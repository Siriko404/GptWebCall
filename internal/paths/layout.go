package paths

import (
	"errors"
	"fmt"
	"path/filepath"
	"strings"
	"time"
	"unicode"
)

const timestampLayout = "2006-01-02_150405"

var windowsReservedNames = map[string]struct{}{
	"CON": {}, "PRN": {}, "AUX": {}, "NUL": {},
	"COM1": {}, "COM2": {}, "COM3": {}, "COM4": {}, "COM5": {}, "COM6": {}, "COM7": {}, "COM8": {}, "COM9": {},
	"LPT1": {}, "LPT2": {}, "LPT3": {}, "LPT4": {}, "LPT5": {}, "LPT6": {}, "LPT7": {}, "LPT8": {}, "LPT9": {},
}

type Layout struct {
	Root    string
	DataDir string
}

func New(root string) (Layout, error) {
	if root == "" || !filepath.IsAbs(root) {
		return Layout{}, errors.New("canonical root must be an absolute path")
	}
	clean := filepath.Clean(root)
	return Layout{Root: clean, DataDir: filepath.Join(clean, "data")}, nil
}

func (l Layout) ProjectDir(projectID string) string {
	if !safeToken(projectID) {
		return ""
	}
	return filepath.Join(l.DataDir, "projects", projectID)
}

func (l Layout) CallDir(projectID, exchangeName string) string {
	projectDir := l.ProjectDir(projectID)
	if projectDir == "" || !safeToken(exchangeName) {
		return ""
	}
	return filepath.Join(projectDir, "calls", exchangeName)
}

func ExchangeName(createdAt time.Time, subject string) (string, error) {
	slug, err := SafeSlug(subject)
	if err != nil {
		return "", fmt.Errorf("subject: %w", err)
	}
	return createdAt.Format(timestampLayout) + "_" + slug, nil
}

func PromptFilename(createdAt time.Time) string {
	return "PROMPT_" + createdAt.Format(timestampLayout) + ".txt"
}

func SafeSlug(value string) (string, error) {
	trimmed := strings.TrimSpace(value)
	if trimmed == "" || trimmed == "." || trimmed == ".." {
		return "", errors.New("slug source is empty or relative")
	}
	if strings.ContainsAny(trimmed, `/\`) {
		return "", errors.New("slug source contains a path separator")
	}
	base := strings.ToUpper(strings.SplitN(strings.TrimRight(trimmed, ". "), ".", 2)[0])
	if _, reserved := windowsReservedNames[base]; reserved {
		return "", fmt.Errorf("slug source uses reserved Windows name %q", base)
	}

	var result strings.Builder
	separatorPending := false
	for _, r := range strings.ToLower(trimmed) {
		if r <= unicode.MaxASCII && (unicode.IsLetter(r) || unicode.IsDigit(r)) {
			if separatorPending && result.Len() > 0 {
				result.WriteByte('_')
			}
			separatorPending = false
			result.WriteRune(r)
			continue
		}
		separatorPending = result.Len() > 0
	}

	slug := strings.Trim(result.String(), "_")
	if slug == "" {
		return "", errors.New("slug contains no ASCII letters or digits")
	}
	if len(slug) > 80 {
		return "", errors.New("slug exceeds 80 characters")
	}
	if _, reserved := windowsReservedNames[strings.ToUpper(slug)]; reserved {
		return "", fmt.Errorf("slug uses reserved Windows name %q", slug)
	}
	return slug, nil
}

func safeToken(value string) bool {
	if value == "" || value == "." || value == ".." || filepath.Base(value) != value || strings.ContainsAny(value, `/\`) {
		return false
	}
	for _, r := range value {
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '_' || r == '-' {
			continue
		}
		return false
	}
	return true
}
