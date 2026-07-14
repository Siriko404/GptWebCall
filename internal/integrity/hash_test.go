package integrity

import (
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/Siriko404/GptWebCall/internal/model"
)

func TestFileSHA256ReturnsDigestAndSize(t *testing.T) {
	path := filepath.Join(t.TempDir(), "fixture.txt")
	if err := os.WriteFile(path, []byte("abc"), 0o600); err != nil {
		t.Fatal(err)
	}

	digest, size, err := FileSHA256(path)
	if err != nil {
		t.Fatal(err)
	}
	if digest != "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad" || size != 3 {
		t.Fatalf("digest=%q size=%d", digest, size)
	}
}

func TestPackageDigestIgnoresDigestFieldAndChangesWithPayload(t *testing.T) {
	manifest := model.PackageManifest{
		SchemaVersion: 1,
		ProjectID:     "project_1",
		CallID:        "call_1",
		CreatedAt:     time.Date(2026, 7, 14, 15, 0, 0, 0, time.UTC),
		Files: []model.PackageFile{{
			FileID:       "file_1",
			Role:         "SOURCE",
			RelativePath: "request/source.txt",
			Size:         3,
			SHA256:       "aaa",
		}},
	}
	first, err := PackageDigest(manifest)
	if err != nil {
		t.Fatal(err)
	}
	manifest.RequestDigest = "ignored-existing-value"
	second, err := PackageDigest(manifest)
	if err != nil {
		t.Fatal(err)
	}
	if first != second || len(first) != 64 {
		t.Fatalf("unstable digest: first=%q second=%q", first, second)
	}
	manifest.Files[0].SHA256 = "bbb"
	third, err := PackageDigest(manifest)
	if err != nil {
		t.Fatal(err)
	}
	if third == first {
		t.Fatal("payload change did not change package digest")
	}
}
