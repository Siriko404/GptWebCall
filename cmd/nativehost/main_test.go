package main

import (
	"path/filepath"
	"reflect"
	"testing"
)

func TestBuildCommandUsesRepositoryRootAndForwardsChromeArguments(t *testing.T) {
	root := filepath.Join("C:", "Projects", "GptWebCall")
	executable := filepath.Join(root, "bin", "gptwebcall-host.exe")
	chromeArguments := []string{"chrome-extension://abcdefghijklmnop/", "--parent-window=10"}

	directory, arguments, err := buildCommand(executable, "python.exe", chromeArguments)
	if err != nil {
		t.Fatal(err)
	}
	want := []string{
		"-m", "companion.native_host", "--root", root,
		"chrome-extension://abcdefghijklmnop/", "--parent-window=10",
	}
	if directory != root || !reflect.DeepEqual(arguments, want) {
		t.Fatalf("directory=%q arguments=%q, want directory=%q arguments=%q", directory, arguments, root, want)
	}
}
