package store

import (
	"os"
	"path/filepath"
	"testing"
)

func TestWriteJSONAtomicLeavesNoTempFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "state.json")
	if err := WriteJSONAtomic(path, map[string]any{"version": 1, "state": "READY"}); err != nil {
		t.Fatal(err)
	}

	var got map[string]any
	if err := ReadJSON(path, &got); err != nil {
		t.Fatal(err)
	}
	if got["version"] != float64(1) || got["state"] != "READY" {
		t.Fatalf("unexpected JSON: %#v", got)
	}

	matches, err := filepath.Glob(path + ".tmp-*")
	if err != nil {
		t.Fatal(err)
	}
	if len(matches) != 0 {
		t.Fatalf("temporary files remain: %v", matches)
	}
}

func TestWriteJSONAtomicPreservesExistingFileWhenEncodingFails(t *testing.T) {
	path := filepath.Join(t.TempDir(), "state.json")
	original := []byte("{\"version\":1}\n")
	if err := os.WriteFile(path, original, 0o600); err != nil {
		t.Fatal(err)
	}

	if err := WriteJSONAtomic(path, map[string]any{"bad": make(chan int)}); err == nil {
		t.Fatal("expected JSON encoding error")
	}
	got, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != string(original) {
		t.Fatalf("existing file changed: %q", got)
	}
}

func TestWriteJSONAtomicReplacesExistingFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "state.json")
	if err := WriteJSONAtomic(path, map[string]any{"version": 1}); err != nil {
		t.Fatal(err)
	}
	if err := WriteJSONAtomic(path, map[string]any{"version": 2}); err != nil {
		t.Fatal(err)
	}

	var got map[string]any
	if err := ReadJSON(path, &got); err != nil {
		t.Fatal(err)
	}
	if got["version"] != float64(2) {
		t.Fatalf("version = %v, want 2", got["version"])
	}
}

func TestReadJSONRejectsTrailingNonWhitespace(t *testing.T) {
	path := filepath.Join(t.TempDir(), "state.json")
	if err := os.WriteFile(path, []byte("{\"version\":1}\n?"), 0o600); err != nil {
		t.Fatal(err)
	}

	var got map[string]any
	if err := ReadJSON(path, &got); err == nil {
		t.Fatal("accepted trailing non-whitespace after JSON value")
	}
}

func TestReadJSONRejectsSecondJSONValue(t *testing.T) {
	path := filepath.Join(t.TempDir(), "state.json")
	if err := os.WriteFile(path, []byte("{\"version\":1}\n{\"version\":2}\n"), 0o600); err != nil {
		t.Fatal(err)
	}

	var got map[string]any
	if err := ReadJSON(path, &got); err == nil {
		t.Fatal("accepted a second JSON value")
	}
}
