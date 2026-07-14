package store

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestSecondWriterCannotAcquireLiveLock(t *testing.T) {
	path := filepath.Join(t.TempDir(), "writer.lock")
	metadata := LockMetadata{
		InstallationID: "installation_1",
		Hostname:       "host-a",
		PID:            os.Getpid(),
		Command:        "test",
		StartedAt:      time.Date(2026, 7, 14, 14, 0, 0, 0, time.UTC),
	}

	first, err := AcquireWriterLock(context.Background(), path, metadata)
	if err != nil {
		t.Fatal(err)
	}
	defer first.Release()

	if _, err := AcquireWriterLock(context.Background(), path, metadata); !errors.Is(err, ErrWriterLocked) {
		t.Fatalf("expected ErrWriterLocked, got %v", err)
	}
}

func TestWriterLockReleaseAllowsNextWriter(t *testing.T) {
	path := filepath.Join(t.TempDir(), "writer.lock")
	metadata := LockMetadata{Hostname: "host-a", PID: os.Getpid(), Command: "test"}

	first, err := AcquireWriterLock(context.Background(), path, metadata)
	if err != nil {
		t.Fatal(err)
	}
	if err := first.Release(); err != nil {
		t.Fatal(err)
	}

	second, err := AcquireWriterLock(context.Background(), path, metadata)
	if err != nil {
		t.Fatalf("next writer could not acquire released lock: %v", err)
	}
	defer second.Release()
}

func TestCancelledContextDoesNotCreateLock(t *testing.T) {
	path := filepath.Join(t.TempDir(), "writer.lock")
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	if _, err := AcquireWriterLock(ctx, path, LockMetadata{}); !errors.Is(err, context.Canceled) {
		t.Fatalf("expected context cancellation, got %v", err)
	}
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Fatalf("cancelled acquisition created a lock: %v", err)
	}
}

func TestAcquireWriterLockRejectsIncompleteMetadata(t *testing.T) {
	for name, metadata := range map[string]LockMetadata{
		"hostname": {PID: os.Getpid(), Command: "test"},
		"pid":      {Hostname: "host-a", Command: "test"},
		"command":  {Hostname: "host-a", PID: os.Getpid()},
	} {
		t.Run(name, func(t *testing.T) {
			path := filepath.Join(t.TempDir(), "writer.lock")
			if _, err := AcquireWriterLock(context.Background(), path, metadata); err == nil {
				t.Fatal("accepted incomplete lock metadata")
			}
			if _, err := os.Stat(path); !os.IsNotExist(err) {
				t.Fatalf("invalid metadata created a lock: %v", err)
			}
		})
	}
}

func TestWriterLockDoesNotRemoveDifferentOwner(t *testing.T) {
	path := filepath.Join(t.TempDir(), "writer.lock")
	lock, err := AcquireWriterLock(context.Background(), path, LockMetadata{
		Hostname: "host-a",
		PID:      os.Getpid(),
		Command:  "test",
	})
	if err != nil {
		t.Fatal(err)
	}

	replacement := LockMetadata{
		Hostname: "host-a",
		PID:      os.Getpid(),
		Command:  "replacement",
		Nonce:    "different-owner",
	}
	if err := WriteJSONAtomic(path, replacement); err != nil {
		t.Fatal(err)
	}

	if err := lock.Release(); !errors.Is(err, ErrLockOwnershipLost) {
		t.Fatalf("expected ErrLockOwnershipLost, got %v", err)
	}
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("different owner's lock was removed: %v", err)
	}
}
