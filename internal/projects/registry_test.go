package projects

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

	"github.com/Siriko404/GptWebCall/internal/model"
	"github.com/Siriko404/GptWebCall/internal/paths"
	"github.com/Siriko404/GptWebCall/internal/store"
)

var fixedTime = time.Date(2026, 7, 14, 15, 0, 0, 0, time.UTC)

func TestRegisterProjectKeepsSourceExternalAndStateGlobal(t *testing.T) {
	root := filepath.Join(t.TempDir(), "GptWebCall")
	layout, err := paths.New(root)
	if err != nil {
		t.Fatal(err)
	}
	hostname, err := os.Hostname()
	if err != nil {
		t.Fatal(err)
	}
	if _, err := Initialize(layout, fixedTime, hostname); err != nil {
		t.Fatal(err)
	}

	source := t.TempDir()
	project, err := Register(layout, RegisterSpec{Name: "Thesis", ExternalRoot: source}, fixedTime)
	if err != nil {
		t.Fatal(err)
	}
	if !filepath.IsAbs(project.ExternalRoot) || project.ExternalRoot != filepath.Clean(source) {
		t.Fatalf("unexpected external root: %+v", project)
	}
	if len(project.AllowedReadRoots) != 1 || project.AllowedReadRoots[0] != project.ExternalRoot {
		t.Fatalf("unexpected default read roots: %+v", project.AllowedReadRoots)
	}
	projectDir := layout.ProjectDir(project.ProjectID)
	if _, err := os.Stat(filepath.Join(projectDir, "PROJECT.json")); err != nil {
		t.Fatal(err)
	}
	if strings.HasPrefix(strings.ToLower(projectDir), strings.ToLower(source+string(os.PathSeparator))) {
		t.Fatal("state leaked into external project")
	}
}

func TestListReturnsRegisteredProjects(t *testing.T) {
	root := filepath.Join(t.TempDir(), "GptWebCall")
	layout, err := paths.New(root)
	if err != nil {
		t.Fatal(err)
	}
	hostname, err := os.Hostname()
	if err != nil {
		t.Fatal(err)
	}
	if _, err := Initialize(layout, fixedTime, hostname); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"Thesis", "Product"} {
		if _, err := Register(layout, RegisterSpec{Name: name, ExternalRoot: t.TempDir()}, fixedTime); err != nil {
			t.Fatal(err)
		}
	}

	projects, err := List(layout)
	if err != nil {
		t.Fatal(err)
	}
	if len(projects) != 2 || projects[0].Name != "Thesis" || projects[1].Name != "Product" {
		t.Fatalf("unexpected projects: %+v", projects)
	}
}

func TestInitializeIsIdempotentForSameRootAndHostname(t *testing.T) {
	root := filepath.Join(t.TempDir(), "GptWebCall")
	layout, err := paths.New(root)
	if err != nil {
		t.Fatal(err)
	}
	hostname, err := os.Hostname()
	if err != nil {
		t.Fatal(err)
	}
	first, err := Initialize(layout, fixedTime, hostname)
	if err != nil {
		t.Fatal(err)
	}
	installationPath := filepath.Join(layout.DataDir, "INSTALLATION.json")
	before, err := os.ReadFile(installationPath)
	if err != nil {
		t.Fatal(err)
	}

	second, err := Initialize(layout, fixedTime.Add(time.Hour), hostname)
	if err != nil {
		t.Fatal(err)
	}
	after, err := os.ReadFile(installationPath)
	if err != nil {
		t.Fatal(err)
	}
	if first.InstallationID != second.InstallationID {
		t.Fatalf("installation ID changed from %q to %q", first.InstallationID, second.InstallationID)
	}
	if string(before) != string(after) {
		t.Fatal("idempotent initialization rewrote installation state")
	}
}

func TestInitializeRejectsDifferentHostnameWithoutChangingState(t *testing.T) {
	root := filepath.Join(t.TempDir(), "GptWebCall")
	layout, err := paths.New(root)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := Initialize(layout, fixedTime, "host-a"); err != nil {
		t.Fatal(err)
	}
	installationPath := filepath.Join(layout.DataDir, "INSTALLATION.json")
	before, err := os.ReadFile(installationPath)
	if err != nil {
		t.Fatal(err)
	}

	if _, err := Initialize(layout, fixedTime.Add(time.Hour), "host-b"); err == nil {
		t.Fatal("accepted a different installation hostname")
	}
	after, err := os.ReadFile(installationPath)
	if err != nil {
		t.Fatal(err)
	}
	if string(before) != string(after) {
		t.Fatal("rejected initialization changed installation state")
	}
}

func TestInitializeRejectsUnsupportedRegistrySchema(t *testing.T) {
	layout, hostname := initializedLayout(t)
	registryPath := filepath.Join(layout.DataDir, "PROJECT_REGISTRY.json")
	var registry model.ProjectRegistry
	if err := store.ReadJSON(registryPath, &registry); err != nil {
		t.Fatal(err)
	}
	registry.SchemaVersion = model.SchemaVersion + 1
	if err := store.WriteJSONAtomic(registryPath, registry); err != nil {
		t.Fatal(err)
	}

	if _, err := Initialize(layout, fixedTime.Add(time.Hour), hostname); err == nil {
		t.Fatal("accepted an unsupported project registry schema")
	}
}

func TestInitializeFailsWhileWriterLockIsHeld(t *testing.T) {
	root := filepath.Join(t.TempDir(), "GptWebCall")
	layout, err := paths.New(root)
	if err != nil {
		t.Fatal(err)
	}
	hostname, err := os.Hostname()
	if err != nil {
		t.Fatal(err)
	}
	lock, err := store.AcquireWriterLock(context.Background(), filepath.Join(layout.DataDir, "locks", "writer.lock"), store.LockMetadata{
		Hostname: hostname,
		PID:      os.Getpid(),
		Command:  "test-holder",
	})
	if err != nil {
		t.Fatal(err)
	}
	defer lock.Release()

	if _, err := Initialize(layout, fixedTime, hostname); !errors.Is(err, store.ErrWriterLocked) {
		t.Fatalf("expected ErrWriterLocked, got %v", err)
	}
	if _, err := os.Stat(filepath.Join(layout.DataDir, "INSTALLATION.json")); !os.IsNotExist(err) {
		t.Fatalf("blocked initialization wrote state: %v", err)
	}
}

func TestRegisterFailsWhileWriterLockIsHeld(t *testing.T) {
	root := filepath.Join(t.TempDir(), "GptWebCall")
	layout, err := paths.New(root)
	if err != nil {
		t.Fatal(err)
	}
	hostname, err := os.Hostname()
	if err != nil {
		t.Fatal(err)
	}
	installation, err := Initialize(layout, fixedTime, hostname)
	if err != nil {
		t.Fatal(err)
	}
	registryPath := filepath.Join(layout.DataDir, "PROJECT_REGISTRY.json")
	before, err := os.ReadFile(registryPath)
	if err != nil {
		t.Fatal(err)
	}
	lock, err := store.AcquireWriterLock(context.Background(), filepath.Join(layout.DataDir, "locks", "writer.lock"), store.LockMetadata{
		InstallationID: installation.InstallationID,
		Hostname:       hostname,
		PID:            os.Getpid(),
		Command:        "test-holder",
	})
	if err != nil {
		t.Fatal(err)
	}
	defer lock.Release()

	if _, err := Register(layout, RegisterSpec{Name: "Thesis", ExternalRoot: t.TempDir()}, fixedTime); !errors.Is(err, store.ErrWriterLocked) {
		t.Fatalf("expected ErrWriterLocked, got %v", err)
	}
	after, err := os.ReadFile(registryPath)
	if err != nil {
		t.Fatal(err)
	}
	if string(before) != string(after) {
		t.Fatal("blocked registration changed registry state")
	}
}

func TestRegisterRejectsDuplicateExternalRoot(t *testing.T) {
	layout, hostname := initializedLayout(t)
	source := t.TempDir()
	if _, err := Register(layout, RegisterSpec{Name: "First", ExternalRoot: source}, fixedTime); err != nil {
		t.Fatal(err)
	}

	if _, err := Register(layout, RegisterSpec{Name: "Duplicate", ExternalRoot: source}, fixedTime.Add(time.Minute)); err == nil {
		t.Fatal("accepted a duplicate external root")
	}
	projects, err := List(layout)
	if err != nil {
		t.Fatal(err)
	}
	if len(projects) != 1 || !strings.EqualFold(projects[0].ExternalRoot, source) {
		t.Fatalf("duplicate attempt changed registry: host=%s projects=%+v", hostname, projects)
	}
}

func TestRegisterRejectsRootInsideGlobalData(t *testing.T) {
	layout, _ := initializedLayout(t)
	source := filepath.Join(layout.DataDir, "external-project")
	if err := os.MkdirAll(source, 0o700); err != nil {
		t.Fatal(err)
	}

	if _, err := Register(layout, RegisterSpec{Name: "Unsafe", ExternalRoot: source}, fixedTime); err == nil {
		t.Fatal("accepted a project root inside global data")
	}
}

func TestRegisterRejectsRegistryFromAnotherInstallation(t *testing.T) {
	layout, _ := initializedLayout(t)
	registryPath := filepath.Join(layout.DataDir, "PROJECT_REGISTRY.json")
	var registry model.ProjectRegistry
	if err := store.ReadJSON(registryPath, &registry); err != nil {
		t.Fatal(err)
	}
	registry.InstallationID = "installation_other"
	if err := store.WriteJSONAtomic(registryPath, registry); err != nil {
		t.Fatal(err)
	}

	if _, err := Register(layout, RegisterSpec{Name: "Thesis", ExternalRoot: t.TempDir()}, fixedTime); err == nil {
		t.Fatal("accepted a registry from another installation")
	}
}

func TestListRejectsRegistryFromAnotherInstallation(t *testing.T) {
	layout, _ := initializedLayout(t)
	registryPath := filepath.Join(layout.DataDir, "PROJECT_REGISTRY.json")
	var registry model.ProjectRegistry
	if err := store.ReadJSON(registryPath, &registry); err != nil {
		t.Fatal(err)
	}
	registry.InstallationID = "installation_other"
	if err := store.WriteJSONAtomic(registryPath, registry); err != nil {
		t.Fatal(err)
	}

	if _, err := List(layout); err == nil {
		t.Fatal("listed projects from another installation")
	}
}

func TestRegisterRejectsMalformedRegistryWithoutChangingEvidence(t *testing.T) {
	layout, _ := initializedLayout(t)
	registryPath := filepath.Join(layout.DataDir, "PROJECT_REGISTRY.json")
	malformed := []byte("{not-json}\n")
	if err := os.WriteFile(registryPath, malformed, 0o600); err != nil {
		t.Fatal(err)
	}
	eventsPath := filepath.Join(layout.DataDir, "EVENTS.jsonl")
	eventsBefore, err := os.ReadFile(eventsPath)
	if err != nil {
		t.Fatal(err)
	}

	if _, err := Register(layout, RegisterSpec{Name: "Thesis", ExternalRoot: t.TempDir()}, fixedTime); err == nil {
		t.Fatal("accepted a malformed project registry")
	}
	registryAfter, err := os.ReadFile(registryPath)
	if err != nil {
		t.Fatal(err)
	}
	eventsAfter, err := os.ReadFile(eventsPath)
	if err != nil {
		t.Fatal(err)
	}
	if string(registryAfter) != string(malformed) || string(eventsAfter) != string(eventsBefore) {
		t.Fatal("rejected registration changed durable evidence")
	}
}

func TestRegisterRejectsNonApprovedHostname(t *testing.T) {
	root := filepath.Join(t.TempDir(), "GptWebCall")
	layout, err := paths.New(root)
	if err != nil {
		t.Fatal(err)
	}
	actualHostname, err := os.Hostname()
	if err != nil {
		t.Fatal(err)
	}
	if _, err := Initialize(layout, fixedTime, actualHostname+"-other"); err != nil {
		t.Fatal(err)
	}

	if _, err := Register(layout, RegisterSpec{Name: "Thesis", ExternalRoot: t.TempDir()}, fixedTime); err == nil {
		t.Fatal("allowed registration from a non-approved hostname")
	}
}

func TestRegisterRejectsLinkedExternalRoot(t *testing.T) {
	layout, _ := initializedLayout(t)
	target := t.TempDir()
	link := filepath.Join(t.TempDir(), "linked-root")
	if err := os.Symlink(target, link); err != nil {
		t.Skipf("directory links unavailable in this environment: %v", err)
	}

	if _, err := Register(layout, RegisterSpec{Name: "Linked", ExternalRoot: link}, fixedTime); err == nil {
		t.Fatal("accepted a linked external root")
	}
}

func TestInitializeAndRegisterAppendBoundEvents(t *testing.T) {
	layout, _ := initializedLayout(t)
	project, err := Register(layout, RegisterSpec{Name: "Thesis", ExternalRoot: t.TempDir()}, fixedTime.Add(time.Minute))
	if err != nil {
		t.Fatal(err)
	}

	eventsPath := filepath.Join(layout.DataDir, "EVENTS.jsonl")
	file, err := os.Open(eventsPath)
	if err != nil {
		t.Fatal(err)
	}
	defer file.Close()

	var events []model.Event
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		var event model.Event
		if err := json.Unmarshal(scanner.Bytes(), &event); err != nil {
			t.Fatal(err)
		}
		events = append(events, event)
	}
	if err := scanner.Err(); err != nil {
		t.Fatal(err)
	}
	if len(events) != 2 {
		t.Fatalf("event count = %d, want 2: %+v", len(events), events)
	}
	if events[0].EventType != "INSTALLATION_INITIALIZED" || events[0].InstallationID == "" {
		t.Fatalf("unexpected initialization event: %+v", events[0])
	}
	if events[1].EventType != "PROJECT_REGISTERED" || events[1].ProjectID != project.ProjectID || events[1].InstallationID != events[0].InstallationID {
		t.Fatalf("unexpected registration event: %+v", events[1])
	}
}

func initializedLayout(t *testing.T) (paths.Layout, string) {
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
	if _, err := Initialize(layout, fixedTime, hostname); err != nil {
		t.Fatal(err)
	}
	return layout, hostname
}
