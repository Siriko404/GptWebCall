package store

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

func AppendEvent(path string, event any) error {
	encoded, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("encode event: %w", err)
	}
	encoded = append(encoded, '\n')

	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return fmt.Errorf("create event directory: %w", err)
	}
	file, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_APPEND, 0o600)
	if err != nil {
		return fmt.Errorf("open event journal: %w", err)
	}
	defer file.Close()

	if _, err := file.Write(encoded); err != nil {
		return fmt.Errorf("append event: %w", err)
	}
	if err := file.Sync(); err != nil {
		return fmt.Errorf("flush event journal: %w", err)
	}
	if err := file.Close(); err != nil {
		return fmt.Errorf("close event journal: %w", err)
	}
	return nil
}
