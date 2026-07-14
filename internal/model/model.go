package model

import "time"

const SchemaVersion = 1

type Installation struct {
	SchemaVersion    int       `json:"schema_version"`
	InstallationID   string    `json:"installation_id"`
	CanonicalRoot    string    `json:"canonical_root"`
	ApprovedHostname string    `json:"approved_hostname"`
	CreatedAt        time.Time `json:"created_at"`
	StateVersion     int64     `json:"state_version"`
}

type Project struct {
	SchemaVersion      int       `json:"schema_version"`
	ProjectID          string    `json:"project_id"`
	Name               string    `json:"name"`
	Objective          string    `json:"objective,omitempty"`
	ExternalRoot       string    `json:"external_root"`
	AllowedReadRoots   []string  `json:"allowed_read_roots"`
	IntegrationRoots   []string  `json:"integration_roots,omitempty"`
	InstructionFiles   []string  `json:"instruction_files,omitempty"`
	SensitivityDefault string    `json:"sensitivity_default,omitempty"`
	RetentionDefault   string    `json:"retention_default,omitempty"`
	CreatedAt          time.Time `json:"created_at"`
	UpdatedAt          time.Time `json:"updated_at"`
	StateVersion       int64     `json:"state_version"`
}

type ProjectRegistry struct {
	SchemaVersion  int       `json:"schema_version"`
	InstallationID string    `json:"installation_id"`
	StateVersion   int64     `json:"state_version"`
	UpdatedAt      time.Time `json:"updated_at"`
	Projects       []Project `json:"projects"`
}

type Event struct {
	SchemaVersion  int            `json:"schema_version"`
	EventID        string         `json:"event_id"`
	EventType      string         `json:"event_type"`
	InstallationID string         `json:"installation_id"`
	ProjectID      string         `json:"project_id,omitempty"`
	OccurredAt     time.Time      `json:"occurred_at"`
	StateVersion   int64          `json:"state_version"`
	Metadata       map[string]any `json:"metadata,omitempty"`
}
