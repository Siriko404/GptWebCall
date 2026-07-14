package calls

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"mime"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/Siriko404/GptWebCall/internal/integrity"
	"github.com/Siriko404/GptWebCall/internal/model"
	"github.com/Siriko404/GptWebCall/internal/paths"
	"github.com/Siriko404/GptWebCall/internal/projects"
	"github.com/Siriko404/GptWebCall/internal/store"
)

type SourceSpec struct {
	Path         string `json:"path"`
	PackagedName string `json:"packaged_name,omitempty"`
	Purpose      string `json:"purpose,omitempty"`
	Authority    string `json:"authority,omitempty"`
	Sensitivity  string `json:"sensitivity,omitempty"`
}

type PrepareSpec struct {
	ProjectID          string       `json:"project_id"`
	Subject            string       `json:"subject"`
	Prompt             string       `json:"prompt"`
	RequestJSONPath    string       `json:"request_json_path"`
	ResponseSchemaPath string       `json:"response_schema_path"`
	Sources            []SourceSpec `json:"sources,omitempty"`
}

func Prepare(layout paths.Layout, spec PrepareSpec, now time.Time) (result model.Call, returnErr error) {
	project, err := findProject(layout, spec.ProjectID)
	if err != nil {
		return model.Call{}, err
	}
	var installation model.Installation
	if err := store.ReadJSON(filepath.Join(layout.DataDir, "INSTALLATION.json"), &installation); err != nil {
		return model.Call{}, fmt.Errorf("read installation: %w", err)
	}
	if installation.SchemaVersion != model.SchemaVersion || !strings.EqualFold(filepath.Clean(installation.CanonicalRoot), filepath.Clean(layout.Root)) {
		return model.Call{}, errors.New("installation identity is invalid")
	}
	hostname, err := os.Hostname()
	if err != nil {
		return model.Call{}, fmt.Errorf("read hostname: %w", err)
	}
	if !strings.EqualFold(installation.ApprovedHostname, hostname) {
		return model.Call{}, errors.New("installation belongs to a different hostname")
	}
	lock, err := store.AcquireWriterLock(context.Background(), filepath.Join(layout.DataDir, "locks", "writer.lock"), store.LockMetadata{
		InstallationID: installation.InstallationID,
		Hostname:       hostname,
		PID:            os.Getpid(),
		Command:        "call-prepare",
		StartedAt:      now.UTC(),
	})
	if err != nil {
		return model.Call{}, err
	}
	defer releaseWriterLock(lock, &returnErr)
	exchangeName, err := paths.ExchangeName(now, spec.Subject)
	if err != nil {
		return model.Call{}, err
	}
	if strings.TrimSpace(spec.Prompt) == "" {
		return model.Call{}, errors.New("prompt is required")
	}
	callID, err := newOpaqueID("call")
	if err != nil {
		return model.Call{}, err
	}
	callDir := layout.CallDir(project.ProjectID, exchangeName)
	if callDir == "" {
		return model.Call{}, errors.New("invalid call path")
	}
	if _, err := os.Stat(callDir); err == nil {
		return model.Call{}, errors.New("call destination already exists")
	} else if !errors.Is(err, os.ErrNotExist) {
		return model.Call{}, fmt.Errorf("inspect call destination: %w", err)
	}

	stagingDir := filepath.Join(layout.DataDir, "staging", callID)
	for _, directory := range []string{"request", "response", "validation", "quarantine"} {
		if err := os.MkdirAll(filepath.Join(stagingDir, directory), 0o700); err != nil {
			return model.Call{}, fmt.Errorf("create call staging directory: %w", err)
		}
	}
	defer func() {
		if returnErr != nil {
			_ = os.RemoveAll(stagingDir)
		}
	}()

	requestDir := filepath.Join(stagingDir, "request")
	files := make([]model.PackageFile, 0, 3+len(spec.Sources))
	governing, err := packageFile(project, spec.RequestJSONPath, requestDir, "WEB_REVIEW_REQUEST.json", "file_001", "GOVERNING_REQUEST", "Web review request", "", "")
	if err != nil {
		return model.Call{}, err
	}
	files = append(files, governing)
	requestID, err := readRequestID(filepath.Join(requestDir, "WEB_REVIEW_REQUEST.json"))
	if err != nil {
		return model.Call{}, err
	}
	responseSchema, err := packageFile(project, spec.ResponseSchemaPath, requestDir, "WEB_RESPONSE_SCHEMA.json", "file_002", "RESPONSE_SCHEMA", "Required response schema", "", "")
	if err != nil {
		return model.Call{}, err
	}
	files = append(files, responseSchema)
	if err := ensureJSONObject(filepath.Join(requestDir, "WEB_RESPONSE_SCHEMA.json"), "response schema"); err != nil {
		return model.Call{}, err
	}

	promptName := paths.PromptFilename(now)
	promptPath := filepath.Join(requestDir, promptName)
	if err := writeFileDurable(promptPath, []byte(spec.Prompt)); err != nil {
		return model.Call{}, err
	}
	promptDigest, promptSize, err := integrity.FileSHA256(promptPath)
	if err != nil {
		return model.Call{}, err
	}
	files = append(files, model.PackageFile{
		FileID:        "file_003",
		Role:          "PROMPT",
		OriginalName:  promptName,
		PackagedName:  promptName,
		RelativePath:  filepath.ToSlash(filepath.Join("request", promptName)),
		Size:          promptSize,
		SHA256:        promptDigest,
		MediaType:     "text/plain; charset=utf-8",
		Purpose:       "Instructions pasted into ChatGPT Web",
		UserDisclosed: true,
	})

	for index, source := range spec.Sources {
		packagedName := source.PackagedName
		if packagedName == "" {
			packagedName = filepath.Base(source.Path)
		}
		packaged, err := packageFile(project, source.Path, requestDir, packagedName, fmt.Sprintf("file_%03d", index+4), "SOURCE", source.Purpose, source.Authority, source.Sensitivity)
		if err != nil {
			return model.Call{}, err
		}
		files = append(files, packaged)
	}

	manifest := model.PackageManifest{
		SchemaVersion: model.SchemaVersion,
		ProjectID:     project.ProjectID,
		CallID:        callID,
		CreatedAt:     now.UTC(),
		ManifestFile:  "request/PACKAGE_MANIFEST.json",
		Files:         files,
	}
	requestDigest, err := integrity.PackageDigest(manifest)
	if err != nil {
		return model.Call{}, err
	}
	manifest.RequestDigest = requestDigest
	if err := store.WriteJSONAtomic(filepath.Join(requestDir, "PACKAGE_MANIFEST.json"), manifest); err != nil {
		return model.Call{}, err
	}
	if err := verifyPackagedFiles(stagingDir, files); err != nil {
		return model.Call{}, err
	}

	call := model.Call{
		SchemaVersion: model.SchemaVersion,
		CallID:        callID,
		ProjectID:     project.ProjectID,
		RequestID:     requestID,
		ExchangeName:  exchangeName,
		Subject:       strings.TrimSpace(spec.Subject),
		State:         model.CallReady,
		StateVersion:  1,
		RequestDigest: requestDigest,
		CreatedAt:     now.UTC(),
		UpdatedAt:     now.UTC(),
	}
	exchange := model.ExchangeManifest{
		SchemaVersion:   model.SchemaVersion,
		ProjectID:       project.ProjectID,
		CallID:          callID,
		RequestID:       requestID,
		ExchangeName:    exchangeName,
		CreatedAt:       now.UTC(),
		DisplayTimezone: now.Location().String(),
		RequestDir:      "request",
		ResponseDir:     "response",
		ValidationDir:   "validation",
		QuarantineDir:   "quarantine",
		PackageManifest: "request/PACKAGE_MANIFEST.json",
		RequestDigest:   requestDigest,
		State:           model.CallReady,
		StateVersion:    1,
	}
	if err := store.WriteJSONAtomic(filepath.Join(stagingDir, "EXCHANGE_MANIFEST.json"), exchange); err != nil {
		return model.Call{}, err
	}
	if err := store.WriteJSONAtomic(filepath.Join(stagingDir, "CALL_STATE.json"), call); err != nil {
		return model.Call{}, err
	}
	eventID, err := newOpaqueID("event")
	if err != nil {
		return model.Call{}, err
	}
	if err := store.AppendEvent(filepath.Join(stagingDir, "EVENTS.jsonl"), model.Event{
		SchemaVersion:  model.SchemaVersion,
		EventID:        eventID,
		EventType:      "CALL_READY",
		InstallationID: installation.InstallationID,
		ProjectID:      project.ProjectID,
		CallID:         callID,
		OccurredAt:     now.UTC(),
		StateVersion:   1,
	}); err != nil {
		return model.Call{}, err
	}

	if err := os.MkdirAll(filepath.Dir(callDir), 0o700); err != nil {
		return model.Call{}, fmt.Errorf("create calls directory: %w", err)
	}
	if err := os.Rename(stagingDir, callDir); err != nil {
		return model.Call{}, fmt.Errorf("promote staged call: %w", err)
	}
	return call, nil
}

func findProject(layout paths.Layout, projectID string) (model.Project, error) {
	registered, err := projects.List(layout)
	if err != nil {
		return model.Project{}, err
	}
	for _, project := range registered {
		if project.ProjectID == projectID {
			return project, nil
		}
	}
	return model.Project{}, fmt.Errorf("project %q is not registered", projectID)
}

func readRequestID(path string) (string, error) {
	var envelope struct {
		RequestID string `json:"request_id"`
	}
	if err := store.ReadJSON(path, &envelope); err != nil {
		return "", fmt.Errorf("read governing request: %w", err)
	}
	requestID := strings.TrimSpace(envelope.RequestID)
	if requestID == "" {
		return "", errors.New("governing request must contain request_id")
	}
	return requestID, nil
}

func ensureJSONObject(path, label string) error {
	var value map[string]any
	if err := store.ReadJSON(path, &value); err != nil {
		return fmt.Errorf("read %s: %w", label, err)
	}
	if value == nil {
		return fmt.Errorf("%s must be a JSON object", label)
	}
	return nil
}

func packageFile(project model.Project, sourcePath, requestDir, packagedName, fileID, role, purpose, authority, sensitivity string) (model.PackageFile, error) {
	if err := validatePackagedName(packagedName, role); err != nil {
		return model.PackageFile{}, err
	}
	absolute, err := filepath.Abs(sourcePath)
	if err != nil {
		return model.PackageFile{}, fmt.Errorf("resolve source file: %w", err)
	}
	linkInfo, err := os.Lstat(absolute)
	if err != nil {
		return model.PackageFile{}, fmt.Errorf("inspect source file: %w", err)
	}
	if linkInfo.Mode()&os.ModeSymlink != 0 {
		return model.PackageFile{}, errors.New("source file must not be a link or reparse point")
	}
	evaluated, err := filepath.EvalSymlinks(absolute)
	if err != nil {
		return model.PackageFile{}, fmt.Errorf("resolve source file links: %w", err)
	}
	if !strings.EqualFold(filepath.Clean(evaluated), filepath.Clean(absolute)) {
		return model.PackageFile{}, errors.New("source file path must not traverse a link or reparse point")
	}
	if !withinAnyRoot(absolute, project.AllowedReadRoots) {
		return model.PackageFile{}, fmt.Errorf("source file is outside approved read roots: %s", filepath.Base(sourcePath))
	}
	info, err := os.Stat(absolute)
	if err != nil {
		return model.PackageFile{}, fmt.Errorf("stat source file: %w", err)
	}
	if !info.Mode().IsRegular() {
		return model.PackageFile{}, errors.New("source must be a regular file")
	}
	destination := filepath.Join(requestDir, packagedName)
	digest, size, err := copyFileVerified(absolute, destination, nil)
	if err != nil {
		return model.PackageFile{}, err
	}
	mediaType := mime.TypeByExtension(strings.ToLower(filepath.Ext(packagedName)))
	if mediaType == "" {
		mediaType = "application/octet-stream"
	}
	return model.PackageFile{
		FileID:        fileID,
		Role:          role,
		OriginalName:  filepath.Base(absolute),
		PackagedName:  packagedName,
		RelativePath:  filepath.ToSlash(filepath.Join("request", packagedName)),
		Size:          size,
		SHA256:        digest,
		MediaType:     mediaType,
		Purpose:       purpose,
		Authority:     authority,
		Sensitivity:   sensitivity,
		UserDisclosed: true,
	}, nil
}

func validatePackagedName(name, role string) error {
	if name == "" || name == "." || name == ".." || filepath.IsAbs(name) || filepath.VolumeName(name) != "" || filepath.Base(name) != name || strings.ContainsAny(name, `/\`) {
		return fmt.Errorf("unsafe packaged filename %q", name)
	}
	if len(name) > 160 || strings.TrimRight(name, ". ") != name {
		return fmt.Errorf("unsafe packaged filename %q", name)
	}
	for _, character := range name {
		if character < 0x20 {
			return fmt.Errorf("unsafe packaged filename %q", name)
		}
	}
	upper := strings.ToUpper(name)
	if role == "SOURCE" {
		reservedFiles := map[string]struct{}{
			"PACKAGE_MANIFEST.JSON":    {},
			"WEB_REVIEW_REQUEST.JSON":  {},
			"WEB_RESPONSE_SCHEMA.JSON": {},
		}
		if _, reserved := reservedFiles[upper]; reserved {
			return fmt.Errorf("packaged filename %q is reserved", name)
		}
		if strings.HasPrefix(upper, "PROMPT_") && strings.HasSuffix(upper, ".TXT") {
			return fmt.Errorf("packaged filename %q is reserved for the generated prompt", name)
		}
	}
	deviceBase := strings.SplitN(strings.TrimRight(upper, ". "), ".", 2)[0]
	if isWindowsDeviceName(deviceBase) {
		return fmt.Errorf("packaged filename %q uses a reserved Windows device name", name)
	}
	return nil
}

func isWindowsDeviceName(name string) bool {
	switch name {
	case "CON", "PRN", "AUX", "NUL":
		return true
	}
	if len(name) == 4 && (strings.HasPrefix(name, "COM") || strings.HasPrefix(name, "LPT")) && name[3] >= '1' && name[3] <= '9' {
		return true
	}
	return false
}

func withinAnyRoot(path string, roots []string) bool {
	for _, root := range roots {
		relative, err := filepath.Rel(filepath.Clean(root), filepath.Clean(path))
		if err == nil && !filepath.IsAbs(relative) && relative != ".." && !strings.HasPrefix(relative, ".."+string(os.PathSeparator)) {
			return true
		}
	}
	return false
}

func copyFileDurable(source, destination string) (returnErr error) {
	input, err := os.Open(source)
	if err != nil {
		return fmt.Errorf("open source file: %w", err)
	}
	defer input.Close()
	output, err := os.OpenFile(destination, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o600)
	if err != nil {
		return fmt.Errorf("create packaged file: %w", err)
	}
	defer func() {
		_ = output.Close()
		if returnErr != nil {
			_ = os.Remove(destination)
		}
	}()
	if _, err := io.Copy(output, input); err != nil {
		return fmt.Errorf("copy packaged file: %w", err)
	}
	if err := output.Sync(); err != nil {
		return fmt.Errorf("flush packaged file: %w", err)
	}
	if err := output.Close(); err != nil {
		return fmt.Errorf("close packaged file: %w", err)
	}
	return nil
}

func copyFileVerified(source, destination string, afterCopy func() error) (string, int64, error) {
	sourceDigestBefore, sourceSizeBefore, err := integrity.FileSHA256(source)
	if err != nil {
		return "", 0, err
	}
	if err := copyFileDurable(source, destination); err != nil {
		return "", 0, err
	}
	if afterCopy != nil {
		if err := afterCopy(); err != nil {
			return "", 0, err
		}
	}
	sourceDigestAfter, sourceSizeAfter, err := integrity.FileSHA256(source)
	if err != nil {
		return "", 0, err
	}
	if sourceDigestBefore != sourceDigestAfter || sourceSizeBefore != sourceSizeAfter {
		return "", 0, fmt.Errorf("source file changed during copy: %s", filepath.Base(source))
	}
	destinationDigest, destinationSize, err := integrity.FileSHA256(destination)
	if err != nil {
		return "", 0, err
	}
	if sourceDigestBefore != destinationDigest || sourceSizeBefore != destinationSize {
		return "", 0, fmt.Errorf("copied file does not match source: %s", filepath.Base(source))
	}
	return destinationDigest, destinationSize, nil
}

func writeFileDurable(path string, contents []byte) (returnErr error) {
	file, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o600)
	if err != nil {
		return fmt.Errorf("create file: %w", err)
	}
	defer func() {
		_ = file.Close()
		if returnErr != nil {
			_ = os.Remove(path)
		}
	}()
	if _, err := file.Write(contents); err != nil {
		return fmt.Errorf("write file: %w", err)
	}
	if err := file.Sync(); err != nil {
		return fmt.Errorf("flush file: %w", err)
	}
	if err := file.Close(); err != nil {
		return fmt.Errorf("close file: %w", err)
	}
	return nil
}

func verifyPackagedFiles(stagingDir string, files []model.PackageFile) error {
	for _, file := range files {
		digest, size, err := integrity.FileSHA256(filepath.Join(stagingDir, filepath.FromSlash(file.RelativePath)))
		if err != nil {
			return err
		}
		if digest != file.SHA256 || size != file.Size {
			return fmt.Errorf("packaged file changed after copy: %s", file.PackagedName)
		}
	}
	return nil
}

func newOpaqueID(prefix string) (string, error) {
	buffer := make([]byte, 16)
	if _, err := rand.Read(buffer); err != nil {
		return "", fmt.Errorf("generate %s ID: %w", prefix, err)
	}
	return prefix + "_" + hex.EncodeToString(buffer), nil
}

func releaseWriterLock(lock *store.WriterLock, returnErr *error) {
	if err := lock.Release(); err != nil && *returnErr == nil {
		*returnErr = fmt.Errorf("release writer lock: %w", err)
	}
}
