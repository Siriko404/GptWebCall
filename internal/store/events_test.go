package store

import (
	"os"
	"path/filepath"
	"testing"
)

func TestAppendEventWritesOneJSONObjectPerLine(t *testing.T) {
	path := filepath.Join(t.TempDir(), "EVENTS.jsonl")
	if err := AppendEvent(path, map[string]any{"event_id": "e1", "version": 1}); err != nil {
		t.Fatal(err)
	}
	if err := AppendEvent(path, map[string]any{"event_id": "e2", "version": 2}); err != nil {
		t.Fatal(err)
	}

	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	want := "{\"event_id\":\"e1\",\"version\":1}\n{\"event_id\":\"e2\",\"version\":2}\n"
	if string(data) != want {
		t.Fatalf("events = %q, want %q", data, want)
	}
}

func TestAppendEventRejectsValuesThatCannotEncode(t *testing.T) {
	path := filepath.Join(t.TempDir(), "EVENTS.jsonl")
	if err := AppendEvent(path, map[string]any{"bad": func() {}}); err == nil {
		t.Fatal("expected encoding error")
	}
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Fatalf("event file should not exist, stat error = %v", err)
	}
}
