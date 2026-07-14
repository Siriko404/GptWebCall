package paths

import (
	"path/filepath"
	"testing"
	"time"
)

func TestExchangeAndPromptShareExactTimestamp(t *testing.T) {
	now := time.Date(2026, 7, 14, 13, 57, 14, 0, time.FixedZone("EDT", -4*60*60))

	exchange, err := ExchangeName(now, "Global standalone architecture")
	if err != nil {
		t.Fatal(err)
	}
	if exchange != "2026-07-14_135714_global_standalone_architecture" {
		t.Fatalf("unexpected exchange name %q", exchange)
	}
	if got := PromptFilename(now); got != "PROMPT_2026-07-14_135714.txt" {
		t.Fatalf("unexpected prompt filename %q", got)
	}
}

func TestSafeSlugRejectsTraversalAndReservedNames(t *testing.T) {
	for _, value := range []string{"../escape", "CON", "a/b", "", ".", "..", "NUL.txt"} {
		t.Run(value, func(t *testing.T) {
			if _, err := SafeSlug(value); err == nil {
				t.Fatalf("accepted unsafe slug %q", value)
			}
		})
	}
}

func TestSafeSlugNormalizesHumanText(t *testing.T) {
	got, err := SafeSlug("  Act 2: Measure & Design Bridge  ")
	if err != nil {
		t.Fatal(err)
	}
	if got != "act_2_measure_design_bridge" {
		t.Fatalf("unexpected slug %q", got)
	}
}

func TestLayoutKeepsOperationalStateUnderCanonicalRoot(t *testing.T) {
	root := filepath.Join(t.TempDir(), "GptWebCall")
	layout, err := New(root)
	if err != nil {
		t.Fatal(err)
	}

	projectDir := layout.ProjectDir("project_abc123")
	callDir := layout.CallDir("project_abc123", "2026-07-14_135714_subject")

	if want := filepath.Join(root, "data", "projects", "project_abc123"); projectDir != want {
		t.Fatalf("project dir %q, want %q", projectDir, want)
	}
	if want := filepath.Join(projectDir, "calls", "2026-07-14_135714_subject"); callDir != want {
		t.Fatalf("call dir %q, want %q", callDir, want)
	}
}

func TestNewRejectsRelativeRoot(t *testing.T) {
	if _, err := New("relative/root"); err == nil {
		t.Fatal("accepted relative canonical root")
	}
}
