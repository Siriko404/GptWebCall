package model

import "time"

const SchemaVersion = 1

const CallReady = "READY"

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
	CallID         string         `json:"call_id,omitempty"`
	OccurredAt     time.Time      `json:"occurred_at"`
	StateVersion   int64          `json:"state_version"`
	Metadata       map[string]any `json:"metadata,omitempty"`
}

type PackageFile struct {
	FileID        string `json:"file_id"`
	Role          string `json:"role"`
	OriginalName  string `json:"original_name"`
	PackagedName  string `json:"packaged_name"`
	RelativePath  string `json:"relative_path"`
	Size          int64  `json:"size"`
	SHA256        string `json:"sha256"`
	MediaType     string `json:"media_type"`
	Purpose       string `json:"purpose,omitempty"`
	Authority     string `json:"authority,omitempty"`
	Sensitivity   string `json:"sensitivity,omitempty"`
	UserDisclosed bool   `json:"user_disclosed"`
}

type PackageManifest struct {
	SchemaVersion int           `json:"schema_version"`
	ProjectID     string        `json:"project_id"`
	CallID        string        `json:"call_id"`
	CreatedAt     time.Time     `json:"created_at"`
	ManifestFile  string        `json:"manifest_file"`
	RequestDigest string        `json:"request_digest,omitempty"`
	Files         []PackageFile `json:"files"`
}

type Call struct {
	SchemaVersion int       `json:"schema_version"`
	CallID        string    `json:"call_id"`
	ProjectID     string    `json:"project_id"`
	RequestID     string    `json:"request_id,omitempty"`
	ExchangeName  string    `json:"exchange_name"`
	Subject       string    `json:"subject"`
	State         string    `json:"state"`
	StateVersion  int64     `json:"state_version"`
	RequestDigest string    `json:"request_digest"`
	CreatedAt     time.Time `json:"created_at"`
	UpdatedAt     time.Time `json:"updated_at"`
}

type ExchangeManifest struct {
	SchemaVersion   int       `json:"schema_version"`
	ProjectID       string    `json:"project_id"`
	CallID          string    `json:"call_id"`
	RequestID       string    `json:"request_id,omitempty"`
	ExchangeName    string    `json:"exchange_name"`
	CreatedAt       time.Time `json:"created_at"`
	DisplayTimezone string    `json:"display_timezone"`
	RequestDir      string    `json:"request_dir"`
	ResponseDir     string    `json:"response_dir"`
	ValidationDir   string    `json:"validation_dir"`
	QuarantineDir   string    `json:"quarantine_dir"`
	PackageManifest string    `json:"package_manifest"`
	RequestDigest   string    `json:"request_digest"`
	State           string    `json:"state"`
	StateVersion    int64     `json:"state_version"`
}
