package store

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

var (
	ErrWriterLocked      = errors.New("writer lock is already held")
	ErrLockOwnershipLost = errors.New("writer lock ownership was lost")
)

type LockMetadata struct {
	InstallationID string    `json:"installation_id,omitempty"`
	Hostname       string    `json:"hostname"`
	PID            int       `json:"pid"`
	Command        string    `json:"command"`
	StartedAt      time.Time `json:"started_at,omitempty"`
	Nonce          string    `json:"nonce"`
}

type WriterLock struct {
	path     string
	nonce    string
	mu       sync.Mutex
	released bool
}

func AcquireWriterLock(ctx context.Context, lockPath string, metadata LockMetadata) (*WriterLock, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	if strings.TrimSpace(metadata.Hostname) == "" {
		return nil, errors.New("lock hostname is required")
	}
	if metadata.PID <= 0 {
		return nil, errors.New("lock PID must be positive")
	}
	if strings.TrimSpace(metadata.Command) == "" {
		return nil, errors.New("lock command is required")
	}
	if metadata.Nonce == "" {
		nonce, err := randomNonce()
		if err != nil {
			return nil, err
		}
		metadata.Nonce = nonce
	}
	if metadata.StartedAt.IsZero() {
		metadata.StartedAt = time.Now().UTC()
	}
	encoded, err := json.MarshalIndent(metadata, "", "  ")
	if err != nil {
		return nil, fmt.Errorf("encode lock metadata: %w", err)
	}
	encoded = append(encoded, '\n')

	if err := os.MkdirAll(filepath.Dir(lockPath), 0o700); err != nil {
		return nil, fmt.Errorf("create lock directory: %w", err)
	}
	file, err := os.OpenFile(lockPath, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o600)
	if err != nil {
		if errors.Is(err, os.ErrExist) {
			return nil, fmt.Errorf("%w: %s", ErrWriterLocked, lockPath)
		}
		return nil, fmt.Errorf("create writer lock: %w", err)
	}
	removeOnFailure := true
	defer func() {
		_ = file.Close()
		if removeOnFailure {
			_ = os.Remove(lockPath)
		}
	}()
	if _, err := file.Write(encoded); err != nil {
		return nil, fmt.Errorf("write lock metadata: %w", err)
	}
	if err := file.Sync(); err != nil {
		return nil, fmt.Errorf("flush writer lock: %w", err)
	}
	if err := file.Close(); err != nil {
		return nil, fmt.Errorf("close writer lock: %w", err)
	}
	removeOnFailure = false
	return &WriterLock{path: lockPath, nonce: metadata.Nonce}, nil
}

func (lock *WriterLock) Release() error {
	lock.mu.Lock()
	defer lock.mu.Unlock()
	if lock.released {
		return nil
	}

	var metadata LockMetadata
	if err := ReadJSON(lock.path, &metadata); err != nil {
		if errors.Is(err, os.ErrNotExist) {
			lock.released = true
			return nil
		}
		return err
	}
	if metadata.Nonce != lock.nonce {
		return ErrLockOwnershipLost
	}
	if err := os.Remove(lock.path); err != nil && !errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("remove writer lock: %w", err)
	}
	lock.released = true
	return nil
}

func randomNonce() (string, error) {
	buffer := make([]byte, 16)
	if _, err := rand.Read(buffer); err != nil {
		return "", fmt.Errorf("generate lock nonce: %w", err)
	}
	return hex.EncodeToString(buffer), nil
}
