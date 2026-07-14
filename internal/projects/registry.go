package projects

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/Siriko404/GptWebCall/internal/model"
	"github.com/Siriko404/GptWebCall/internal/paths"
	"github.com/Siriko404/GptWebCall/internal/store"
)

type RegisterSpec struct {
	Name               string   `json:"name"`
	Objective          string   `json:"objective,omitempty"`
	ExternalRoot       string   `json:"external_root"`
	AllowedReadRoots   []string `json:"allowed_read_roots,omitempty"`
	IntegrationRoots   []string `json:"integration_roots,omitempty"`
	InstructionFiles   []string `json:"instruction_files,omitempty"`
	SensitivityDefault string   `json:"sensitivity_default,omitempty"`
	RetentionDefault   string   `json:"retention_default,omitempty"`
}

func Initialize(layout paths.Layout, now time.Time, hostname string) (result model.Installation, returnErr error) {
	if strings.TrimSpace(hostname) == "" {
		return model.Installation{}, errors.New("hostname is required")
	}
	lock, err := store.AcquireWriterLock(context.Background(), writerLockPath(layout), store.LockMetadata{
		Hostname:  hostname,
		PID:       os.Getpid(),
		Command:   "initialize",
		StartedAt: now.UTC(),
	})
	if err != nil {
		return model.Installation{}, err
	}
	defer releaseWriterLock(lock, &returnErr)

	installationPath := filepath.Join(layout.DataDir, "INSTALLATION.json")
	registryPath := filepath.Join(layout.DataDir, "PROJECT_REGISTRY.json")
	var existing model.Installation
	if err := store.ReadJSON(installationPath, &existing); err == nil {
		if existing.SchemaVersion != model.SchemaVersion {
			return model.Installation{}, fmt.Errorf("unsupported installation schema version %d", existing.SchemaVersion)
		}
		if !samePath(existing.CanonicalRoot, layout.Root) {
			return model.Installation{}, errors.New("installation canonical root does not match")
		}
		if !strings.EqualFold(existing.ApprovedHostname, hostname) {
			return model.Installation{}, errors.New("installation belongs to a different hostname")
		}
		var registry model.ProjectRegistry
		if err := store.ReadJSON(registryPath, &registry); err != nil {
			return model.Installation{}, fmt.Errorf("read project registry: %w", err)
		}
		if registry.SchemaVersion != model.SchemaVersion {
			return model.Installation{}, fmt.Errorf("unsupported project registry schema version %d", registry.SchemaVersion)
		}
		if registry.InstallationID != existing.InstallationID {
			return model.Installation{}, errors.New("project registry installation ID does not match")
		}
		return existing, nil
	} else if !errors.Is(err, os.ErrNotExist) {
		return model.Installation{}, fmt.Errorf("read installation: %w", err)
	}

	installationID, err := newID("installation")
	if err != nil {
		return model.Installation{}, err
	}
	installation := model.Installation{
		SchemaVersion:    model.SchemaVersion,
		InstallationID:   installationID,
		CanonicalRoot:    layout.Root,
		ApprovedHostname: hostname,
		CreatedAt:        now.UTC(),
		StateVersion:     1,
	}
	registry := model.ProjectRegistry{
		SchemaVersion:  model.SchemaVersion,
		InstallationID: installationID,
		StateVersion:   1,
		UpdatedAt:      now.UTC(),
		Projects:       []model.Project{},
	}
	eventID, err := newID("event")
	if err != nil {
		return model.Installation{}, err
	}
	event := model.Event{
		SchemaVersion:  model.SchemaVersion,
		EventID:        eventID,
		EventType:      "INSTALLATION_INITIALIZED",
		InstallationID: installationID,
		OccurredAt:     now.UTC(),
		StateVersion:   1,
	}
	if err := store.AppendEvent(globalEventsPath(layout), event); err != nil {
		return model.Installation{}, err
	}
	if err := store.WriteJSONAtomic(installationPath, installation); err != nil {
		return model.Installation{}, err
	}
	if err := store.WriteJSONAtomic(registryPath, registry); err != nil {
		return model.Installation{}, err
	}
	return installation, nil
}

func Register(layout paths.Layout, spec RegisterSpec, now time.Time) (result model.Project, returnErr error) {
	name := strings.TrimSpace(spec.Name)
	if name == "" {
		return model.Project{}, errors.New("project name is required")
	}
	externalRoot, err := canonicalDirectory(spec.ExternalRoot)
	if err != nil {
		return model.Project{}, err
	}
	if pathWithin(layout.DataDir, externalRoot) {
		return model.Project{}, errors.New("external root must not be inside global data")
	}

	var installation model.Installation
	if err := store.ReadJSON(filepath.Join(layout.DataDir, "INSTALLATION.json"), &installation); err != nil {
		return model.Project{}, fmt.Errorf("read installation: %w", err)
	}
	if installation.SchemaVersion != model.SchemaVersion {
		return model.Project{}, fmt.Errorf("unsupported installation schema version %d", installation.SchemaVersion)
	}
	if !samePath(installation.CanonicalRoot, layout.Root) {
		return model.Project{}, errors.New("installation canonical root does not match")
	}
	hostname, err := os.Hostname()
	if err != nil {
		return model.Project{}, fmt.Errorf("read hostname: %w", err)
	}
	if !strings.EqualFold(installation.ApprovedHostname, hostname) {
		return model.Project{}, errors.New("installation belongs to a different hostname")
	}
	lock, err := store.AcquireWriterLock(context.Background(), writerLockPath(layout), store.LockMetadata{
		InstallationID: installation.InstallationID,
		Hostname:       hostname,
		PID:            os.Getpid(),
		Command:        "project-register",
		StartedAt:      now.UTC(),
	})
	if err != nil {
		return model.Project{}, err
	}
	defer releaseWriterLock(lock, &returnErr)

	var registry model.ProjectRegistry
	if err := store.ReadJSON(filepath.Join(layout.DataDir, "PROJECT_REGISTRY.json"), &registry); err != nil {
		return model.Project{}, fmt.Errorf("read project registry: %w", err)
	}
	if registry.SchemaVersion != model.SchemaVersion {
		return model.Project{}, fmt.Errorf("unsupported project registry schema version %d", registry.SchemaVersion)
	}
	if registry.InstallationID != installation.InstallationID {
		return model.Project{}, errors.New("project registry installation ID does not match")
	}
	for _, existing := range registry.Projects {
		if samePath(existing.ExternalRoot, externalRoot) {
			return model.Project{}, fmt.Errorf("external root is already registered to project %s", existing.ProjectID)
		}
	}

	projectID, err := newID("project")
	if err != nil {
		return model.Project{}, err
	}
	allowedReadRoots := append([]string(nil), spec.AllowedReadRoots...)
	if len(allowedReadRoots) == 0 {
		allowedReadRoots = []string{externalRoot}
	}
	project := model.Project{
		SchemaVersion:      model.SchemaVersion,
		ProjectID:          projectID,
		Name:               name,
		Objective:          strings.TrimSpace(spec.Objective),
		ExternalRoot:       externalRoot,
		AllowedReadRoots:   allowedReadRoots,
		IntegrationRoots:   append([]string(nil), spec.IntegrationRoots...),
		InstructionFiles:   append([]string(nil), spec.InstructionFiles...),
		SensitivityDefault: spec.SensitivityDefault,
		RetentionDefault:   spec.RetentionDefault,
		CreatedAt:          now.UTC(),
		UpdatedAt:          now.UTC(),
		StateVersion:       1,
	}
	registry.Projects = append(registry.Projects, project)
	registry.StateVersion++
	registry.UpdatedAt = now.UTC()
	eventID, err := newID("event")
	if err != nil {
		return model.Project{}, err
	}
	event := model.Event{
		SchemaVersion:  model.SchemaVersion,
		EventID:        eventID,
		EventType:      "PROJECT_REGISTERED",
		InstallationID: installation.InstallationID,
		ProjectID:      projectID,
		OccurredAt:     now.UTC(),
		StateVersion:   registry.StateVersion,
		Metadata: map[string]any{
			"project_name": project.Name,
		},
	}
	if err := store.AppendEvent(globalEventsPath(layout), event); err != nil {
		return model.Project{}, err
	}
	if err := store.WriteJSONAtomic(filepath.Join(layout.ProjectDir(projectID), "PROJECT.json"), project); err != nil {
		return model.Project{}, err
	}
	if err := store.WriteJSONAtomic(filepath.Join(layout.DataDir, "PROJECT_REGISTRY.json"), registry); err != nil {
		return model.Project{}, err
	}
	return project, nil
}

func List(layout paths.Layout) ([]model.Project, error) {
	var installation model.Installation
	if err := store.ReadJSON(filepath.Join(layout.DataDir, "INSTALLATION.json"), &installation); err != nil {
		return nil, fmt.Errorf("read installation: %w", err)
	}
	if installation.SchemaVersion != model.SchemaVersion || !samePath(installation.CanonicalRoot, layout.Root) {
		return nil, errors.New("installation identity is invalid")
	}
	var registry model.ProjectRegistry
	if err := store.ReadJSON(filepath.Join(layout.DataDir, "PROJECT_REGISTRY.json"), &registry); err != nil {
		return nil, fmt.Errorf("read project registry: %w", err)
	}
	if registry.SchemaVersion != model.SchemaVersion || registry.InstallationID != installation.InstallationID {
		return nil, errors.New("project registry identity is invalid")
	}
	return append([]model.Project(nil), registry.Projects...), nil
}

func canonicalDirectory(path string) (string, error) {
	if strings.TrimSpace(path) == "" {
		return "", errors.New("external root is required")
	}
	absolute, err := filepath.Abs(path)
	if err != nil {
		return "", fmt.Errorf("resolve external root: %w", err)
	}
	linkInfo, err := os.Lstat(absolute)
	if err != nil {
		return "", fmt.Errorf("inspect external root: %w", err)
	}
	if linkInfo.Mode()&os.ModeSymlink != 0 {
		return "", errors.New("external root must not be a link or reparse point")
	}
	evaluated, err := filepath.EvalSymlinks(absolute)
	if err != nil {
		return "", fmt.Errorf("resolve external root links: %w", err)
	}
	if !samePath(evaluated, absolute) {
		return "", errors.New("external root must not traverse a link or reparse point")
	}
	info, err := os.Stat(absolute)
	if err != nil {
		return "", fmt.Errorf("stat external root: %w", err)
	}
	if !info.IsDir() {
		return "", errors.New("external root must be a directory")
	}
	return filepath.Clean(absolute), nil
}

func samePath(left, right string) bool {
	return strings.EqualFold(filepath.Clean(left), filepath.Clean(right))
}

func pathWithin(parent, child string) bool {
	if samePath(parent, child) {
		return true
	}
	relative, err := filepath.Rel(filepath.Clean(parent), filepath.Clean(child))
	if err != nil || filepath.IsAbs(relative) {
		return false
	}
	return relative != ".." && !strings.HasPrefix(relative, ".."+string(os.PathSeparator))
}

func writerLockPath(layout paths.Layout) string {
	return filepath.Join(layout.DataDir, "locks", "writer.lock")
}

func globalEventsPath(layout paths.Layout) string {
	return filepath.Join(layout.DataDir, "EVENTS.jsonl")
}

func releaseWriterLock(lock *store.WriterLock, returnErr *error) {
	if err := lock.Release(); err != nil && *returnErr == nil {
		*returnErr = fmt.Errorf("release writer lock: %w", err)
	}
}

func newID(prefix string) (string, error) {
	buffer := make([]byte, 16)
	if _, err := rand.Read(buffer); err != nil {
		return "", fmt.Errorf("generate %s ID: %w", prefix, err)
	}
	return prefix + "_" + hex.EncodeToString(buffer), nil
}
