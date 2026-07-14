package calls

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/Siriko404/GptWebCall/internal/integrity"
	"github.com/Siriko404/GptWebCall/internal/model"
	"github.com/Siriko404/GptWebCall/internal/paths"
	"github.com/Siriko404/GptWebCall/internal/projects"
	"github.com/Siriko404/GptWebCall/internal/store"
)

func TestPrepareCreatesFrozenSelfContainedExchange(t *testing.T) {
	root := filepath.Join(t.TempDir(), "GptWebCall")
	layout, err := paths.New(root)
	if err != nil {
		t.Fatal(err)
	}
	hostname, err := os.Hostname()
	if err != nil {
		t.Fatal(err)
	}
	if _, err := projects.Initialize(layout, time.Date(2026, 7, 14, 14, 0, 0, 0, time.UTC), hostname); err != nil {
		t.Fatal(err)
	}
	externalRoot := t.TempDir()
	project, err := projects.Register(layout, projects.RegisterSpec{Name: "Thesis", ExternalRoot: externalRoot}, time.Date(2026, 7, 14, 14, 1, 0, 0, time.UTC))
	if err != nil {
		t.Fatal(err)
	}

	sourcePath := writeFixture(t, externalRoot, "thesis_excerpt.txt", "thesis evidence\n")
	requestPath := writeFixture(t, externalRoot, "request.json", "{\"request_id\":\"request_1\"}\n")
	responseSchemaPath := writeFixture(t, externalRoot, "response_schema.json", "{\"type\":\"object\"}\n")
	createdAt := time.Date(2026, 7, 14, 15, 4, 5, 0, time.FixedZone("EDT", -4*60*60))

	call, err := Prepare(layout, PrepareSpec{
		ProjectID:          project.ProjectID,
		Subject:            "Contribution review",
		Prompt:             "Read the attached package and return the required files only.",
		RequestJSONPath:    requestPath,
		ResponseSchemaPath: responseSchemaPath,
		Sources: []SourceSpec{{
			Path:        sourcePath,
			Purpose:     "Authoritative thesis evidence",
			Authority:   "PRIMARY",
			Sensitivity: "INTERNAL",
		}},
	}, createdAt)
	if err != nil {
		t.Fatal(err)
	}

	wantExchange := "2026-07-14_150405_contribution_review"
	if call.ExchangeName != wantExchange {
		t.Fatalf("exchange = %q, want %q", call.ExchangeName, wantExchange)
	}
	callDir := layout.CallDir(project.ProjectID, call.ExchangeName)
	promptName := "PROMPT_2026-07-14_150405.txt"
	if _, err := os.Stat(filepath.Join(callDir, "request", promptName)); err != nil {
		t.Fatalf("timestamped prompt missing: %v", err)
	}

	var manifest model.PackageManifest
	if err := store.ReadJSON(filepath.Join(callDir, "request", "PACKAGE_MANIFEST.json"), &manifest); err != nil {
		t.Fatal(err)
	}
	if len(manifest.Files) != 4 {
		t.Fatalf("manifest file count = %d, want 4", len(manifest.Files))
	}
	for _, file := range manifest.Files {
		if file.Size <= 0 || len(file.SHA256) != 64 {
			t.Fatalf("file lacks size/hash: %+v", file)
		}
		storedPath := filepath.Join(callDir, filepath.FromSlash(file.RelativePath))
		digest, size, err := integrity.FileSHA256(storedPath)
		if err != nil {
			t.Fatal(err)
		}
		if digest != file.SHA256 || size != file.Size {
			t.Fatalf("manifest mismatch for %s", file.RelativePath)
		}
	}

	var state model.Call
	if err := store.ReadJSON(filepath.Join(callDir, "CALL_STATE.json"), &state); err != nil {
		t.Fatal(err)
	}
	if state.State != model.CallReady || state.RequestDigest == "" || state.RequestID != "request_1" {
		t.Fatalf("call not ready: %+v", state)
	}
	if _, err := os.Stat(filepath.Join(externalRoot, "PROJECT.json")); !os.IsNotExist(err) {
		t.Fatalf("infrastructure leaked into external project: %v", err)
	}
	var installation model.Installation
	if err := store.ReadJSON(filepath.Join(layout.DataDir, "INSTALLATION.json"), &installation); err != nil {
		t.Fatal(err)
	}
	eventFile, err := os.Open(filepath.Join(callDir, "EVENTS.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	defer eventFile.Close()
	scanner := bufio.NewScanner(eventFile)
	if !scanner.Scan() {
		t.Fatal("missing call event")
	}
	var event model.Event
	if err := json.Unmarshal(scanner.Bytes(), &event); err != nil {
		t.Fatal(err)
	}
	if event.InstallationID != installation.InstallationID || event.CallID != call.CallID {
		t.Fatalf("event is not bound to its installation/call: %+v", event)
	}
}

func TestPrepareRejectsUnsafePackagedNames(t *testing.T) {
	for name, packagedName := range map[string]string{
		"traversal":        filepath.Join("..", "escape.txt"),
		"absolute":         `C:\escape.txt`,
		"reserved":         "CON",
		"prompt_lookalike": "PROMPT_2026-07-14_000000.txt",
	} {
		t.Run(name, func(t *testing.T) {
			fixture := newCallFixture(t)
			source := writeFixture(t, fixture.externalRoot, "source.txt", "evidence\n")
			spec := fixture.prepareSpec()
			spec.Sources = []SourceSpec{{Path: source, PackagedName: packagedName}}

			if _, err := Prepare(fixture.layout, spec, fixture.createdAt); err == nil {
				t.Fatalf("accepted unsafe packaged name %q", packagedName)
			}
			if _, err := os.Stat(fixture.layout.CallDir(fixture.project.ProjectID, fixture.exchangeName(t))); !os.IsNotExist(err) {
				t.Fatalf("unsafe package left a call destination: %v", err)
			}
		})
	}
}

func TestPrepareRejectsLinkedSourceFile(t *testing.T) {
	fixture := newCallFixture(t)
	target := writeFixture(t, fixture.externalRoot, "target.txt", "evidence\n")
	link := filepath.Join(fixture.externalRoot, "linked.txt")
	if err := os.Symlink(target, link); err != nil {
		t.Skipf("file links unavailable in this environment: %v", err)
	}
	spec := fixture.prepareSpec()
	spec.Sources = []SourceSpec{{Path: link}}

	if _, err := Prepare(fixture.layout, spec, fixture.createdAt); err == nil {
		t.Fatal("accepted a linked source file")
	} else if !strings.Contains(strings.ToLower(err.Error()), "link") && !strings.Contains(strings.ToLower(err.Error()), "reparse") {
		t.Fatalf("linked source was rejected for the wrong reason: %v", err)
	}
}

func TestPrepareFailsWhileWriterLockIsHeld(t *testing.T) {
	fixture := newCallFixture(t)
	var installation model.Installation
	if err := store.ReadJSON(filepath.Join(fixture.layout.DataDir, "INSTALLATION.json"), &installation); err != nil {
		t.Fatal(err)
	}
	hostname, err := os.Hostname()
	if err != nil {
		t.Fatal(err)
	}
	lock, err := store.AcquireWriterLock(context.Background(), filepath.Join(fixture.layout.DataDir, "locks", "writer.lock"), store.LockMetadata{
		InstallationID: installation.InstallationID,
		Hostname:       hostname,
		PID:            os.Getpid(),
		Command:        "test-holder",
	})
	if err != nil {
		t.Fatal(err)
	}
	defer lock.Release()

	if _, err := Prepare(fixture.layout, fixture.prepareSpec(), fixture.createdAt); !errors.Is(err, store.ErrWriterLocked) {
		t.Fatalf("expected ErrWriterLocked, got %v", err)
	}
	if _, err := os.Stat(fixture.layout.CallDir(fixture.project.ProjectID, fixture.exchangeName(t))); !os.IsNotExist(err) {
		t.Fatalf("blocked preparation left a call destination: %v", err)
	}
}

func TestPrepareRejectsNonApprovedHostname(t *testing.T) {
	fixture := newCallFixture(t)
	installationPath := filepath.Join(fixture.layout.DataDir, "INSTALLATION.json")
	var installation model.Installation
	if err := store.ReadJSON(installationPath, &installation); err != nil {
		t.Fatal(err)
	}
	installation.ApprovedHostname = "another-host"
	if err := store.WriteJSONAtomic(installationPath, installation); err != nil {
		t.Fatal(err)
	}

	if _, err := Prepare(fixture.layout, fixture.prepareSpec(), fixture.createdAt); err == nil {
		t.Fatal("allowed preparation from a non-approved hostname")
	}
}

func TestPrepareRejectsMalformedResponseSchema(t *testing.T) {
	fixture := newCallFixture(t)
	if err := os.WriteFile(fixture.responseSchemaPath, []byte("{not-json}\n"), 0o600); err != nil {
		t.Fatal(err)
	}

	if _, err := Prepare(fixture.layout, fixture.prepareSpec(), fixture.createdAt); err == nil {
		t.Fatal("accepted a malformed response schema")
	}
}

func TestPrepareLeavesNoReadyCallWhenStagingCreationFails(t *testing.T) {
	fixture := newCallFixture(t)
	if err := os.WriteFile(filepath.Join(fixture.layout.DataDir, "staging"), []byte("not a directory"), 0o600); err != nil {
		t.Fatal(err)
	}

	if _, err := Prepare(fixture.layout, fixture.prepareSpec(), fixture.createdAt); err == nil {
		t.Fatal("accepted preparation despite an unavailable staging directory")
	}
	if _, err := os.Stat(fixture.layout.CallDir(fixture.project.ProjectID, fixture.exchangeName(t))); !os.IsNotExist(err) {
		t.Fatalf("staging failure left a call destination: %v", err)
	}
}

func TestPrepareRejectsSourceOutsideApprovedRoots(t *testing.T) {
	fixture := newCallFixture(t)
	spec := fixture.prepareSpec()
	spec.Sources = []SourceSpec{{Path: writeFixture(t, t.TempDir(), "outside.txt", "outside\n")}}

	if _, err := Prepare(fixture.layout, spec, fixture.createdAt); err == nil {
		t.Fatal("accepted a source outside approved read roots")
	}
	if _, err := os.Stat(fixture.layout.CallDir(fixture.project.ProjectID, fixture.exchangeName(t))); !os.IsNotExist(err) {
		t.Fatalf("outside source left a call destination: %v", err)
	}
}

func TestPrepareRejectsDuplicatePackagedSourceNames(t *testing.T) {
	fixture := newCallFixture(t)
	firstDir := filepath.Join(fixture.externalRoot, "one")
	secondDir := filepath.Join(fixture.externalRoot, "two")
	if err := os.MkdirAll(firstDir, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(secondDir, 0o700); err != nil {
		t.Fatal(err)
	}
	spec := fixture.prepareSpec()
	spec.Sources = []SourceSpec{
		{Path: writeFixture(t, firstDir, "same.txt", "first\n")},
		{Path: writeFixture(t, secondDir, "same.txt", "second\n")},
	}

	if _, err := Prepare(fixture.layout, spec, fixture.createdAt); err == nil {
		t.Fatal("accepted duplicate packaged source names")
	}
	if _, err := os.Stat(fixture.layout.CallDir(fixture.project.ProjectID, fixture.exchangeName(t))); !os.IsNotExist(err) {
		t.Fatalf("duplicate sources left a call destination: %v", err)
	}
}

func TestPrepareRejectsExistingCallDestination(t *testing.T) {
	fixture := newCallFixture(t)
	first, err := Prepare(fixture.layout, fixture.prepareSpec(), fixture.createdAt)
	if err != nil {
		t.Fatal(err)
	}
	statePath := filepath.Join(fixture.layout.CallDir(fixture.project.ProjectID, first.ExchangeName), "CALL_STATE.json")
	before, err := os.ReadFile(statePath)
	if err != nil {
		t.Fatal(err)
	}

	if _, err := Prepare(fixture.layout, fixture.prepareSpec(), fixture.createdAt); err == nil {
		t.Fatal("accepted an existing call destination")
	}
	after, err := os.ReadFile(statePath)
	if err != nil {
		t.Fatal(err)
	}
	if string(before) != string(after) {
		t.Fatal("existing call state changed after a rejected prepare")
	}
}

func TestCopyFileVerifiedRejectsSourceChangedAfterCopy(t *testing.T) {
	directory := t.TempDir()
	source := writeFixture(t, directory, "source.txt", "first\n")
	destination := filepath.Join(directory, "copy.txt")

	if _, _, err := copyFileVerified(source, destination, func() error {
		return os.WriteFile(source, []byte("second\n"), 0o600)
	}); err == nil {
		t.Fatal("accepted a source changed after copy")
	}
}

type callFixture struct {
	layout             paths.Layout
	project            model.Project
	externalRoot       string
	requestPath        string
	responseSchemaPath string
	createdAt          time.Time
}

func newCallFixture(t *testing.T) callFixture {
	t.Helper()
	root := filepath.Join(t.TempDir(), "GptWebCall")
	layout, err := paths.New(root)
	if err != nil {
		t.Fatal(err)
	}
	hostname, err := os.Hostname()
	if err != nil {
		t.Fatal(err)
	}
	if _, err := projects.Initialize(layout, time.Date(2026, 7, 14, 14, 0, 0, 0, time.UTC), hostname); err != nil {
		t.Fatal(err)
	}
	externalRoot := t.TempDir()
	project, err := projects.Register(layout, projects.RegisterSpec{Name: "Fixture", ExternalRoot: externalRoot}, time.Date(2026, 7, 14, 14, 1, 0, 0, time.UTC))
	if err != nil {
		t.Fatal(err)
	}
	return callFixture{
		layout:             layout,
		project:            project,
		externalRoot:       externalRoot,
		requestPath:        writeFixture(t, externalRoot, "request.json", "{\"request_id\":\"request_fixture\"}\n"),
		responseSchemaPath: writeFixture(t, externalRoot, "response_schema.json", "{\"type\":\"object\"}\n"),
		createdAt:          time.Date(2026, 7, 14, 15, 4, 5, 0, time.FixedZone("EDT", -4*60*60)),
	}
}

func (fixture callFixture) prepareSpec() PrepareSpec {
	return PrepareSpec{
		ProjectID:          fixture.project.ProjectID,
		Subject:            "Fixture call",
		Prompt:             "Return the required files only.",
		RequestJSONPath:    fixture.requestPath,
		ResponseSchemaPath: fixture.responseSchemaPath,
	}
}

func (fixture callFixture) exchangeName(t *testing.T) string {
	t.Helper()
	name, err := paths.ExchangeName(fixture.createdAt, "Fixture call")
	if err != nil {
		t.Fatal(err)
	}
	return name
}

func writeFixture(t *testing.T, directory, name, contents string) string {
	t.Helper()
	path := filepath.Join(directory, name)
	if err := os.WriteFile(path, []byte(contents), 0o600); err != nil {
		t.Fatal(err)
	}
	return path
}
