package integrity

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"

	"github.com/Siriko404/GptWebCall/internal/model"
)

func FileSHA256(path string) (string, int64, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", 0, fmt.Errorf("open file for hashing: %w", err)
	}
	defer file.Close()

	hash := sha256.New()
	size, err := io.Copy(hash, file)
	if err != nil {
		return "", 0, fmt.Errorf("hash file: %w", err)
	}
	return hex.EncodeToString(hash.Sum(nil)), size, nil
}

func PackageDigest(manifest model.PackageManifest) (string, error) {
	manifest.RequestDigest = ""
	encoded, err := json.Marshal(manifest)
	if err != nil {
		return "", fmt.Errorf("encode package manifest for digest: %w", err)
	}
	digest := sha256.Sum256(encoded)
	return hex.EncodeToString(digest[:]), nil
}
