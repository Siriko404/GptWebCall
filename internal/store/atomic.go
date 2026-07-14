package store

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
)

func WriteJSONAtomic(path string, value any) (returnErr error) {
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return fmt.Errorf("create parent directory: %w", err)
	}

	temp, err := os.CreateTemp(filepath.Dir(path), filepath.Base(path)+".tmp-*")
	if err != nil {
		return fmt.Errorf("create temporary file: %w", err)
	}
	tempPath := temp.Name()
	defer func() {
		_ = temp.Close()
		if returnErr != nil {
			_ = os.Remove(tempPath)
		}
	}()

	if err := temp.Chmod(0o600); err != nil {
		return fmt.Errorf("restrict temporary file: %w", err)
	}
	encoder := json.NewEncoder(temp)
	encoder.SetEscapeHTML(false)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(value); err != nil {
		return fmt.Errorf("encode JSON: %w", err)
	}
	if err := temp.Sync(); err != nil {
		return fmt.Errorf("flush temporary file: %w", err)
	}
	if err := temp.Close(); err != nil {
		return fmt.Errorf("close temporary file: %w", err)
	}
	if err := os.Rename(tempPath, path); err != nil {
		return fmt.Errorf("replace destination atomically: %w", err)
	}
	return nil
}

func ReadJSON(path string, target any) error {
	file, err := os.Open(path)
	if err != nil {
		return fmt.Errorf("open JSON: %w", err)
	}
	defer file.Close()

	decoder := json.NewDecoder(file)
	if err := decoder.Decode(target); err != nil {
		return fmt.Errorf("decode JSON: %w", err)
	}
	var extra any
	if err := decoder.Decode(&extra); err == nil {
		return fmt.Errorf("decode JSON: multiple values in %s", path)
	} else if err != io.EOF {
		return fmt.Errorf("decode JSON trailing data: %w", err)
	}
	return nil
}
