package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"runtime"
)

// Define a sentinel error to stop walking
var errStopWalk = errors.New("stop walk")

type SystemSnapshot struct {
	RegistryKeys []string `json:"registry_keys"`
	Files        []string `json:"files"`
}

func scanDirectory(root string, result *[]string, maxItems int) {
	_ = filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil
		}
		if len(*result) >= maxItems {
			return errStopWalk
		}
		if !info.IsDir() {
			*result = append(*result, path)
		}
		return nil
	})
}

func getPlatformScanDirs() []string {
	var dirs []string
	switch runtime.GOOS {
	case "windows":
		dirs = []string{
			os.Getenv("APPDATA"),
			os.Getenv("LOCALAPPDATA"),
			"C:\\Program Files",
			"C:\\Program Files (x86)",
		}
	case "darwin":
		dirs = []string{
			"/Applications",
			filepath.Join(os.Getenv("HOME"), "Applications"),
			"/Library/Application Support",
			filepath.Join(os.Getenv("HOME"), "Library/Application Support"),
		}
	case "linux":
		dirs = []string{
			"/usr/bin",
			"/usr/share",
			"/var/lib",
			filepath.Join(os.Getenv("HOME"), ".local/share"),
			filepath.Join(os.Getenv("HOME"), ".config"),
		}
	}
	return dirs
}

func main() {
	mode := flag.String("mode", "scan", "Running mode: scan or delete")
	targetFile := flag.String("out", "snapshot.json", "Output or input snapshot log path")
	flag.Parse()

	if *mode == "scan" {
		snap := SystemSnapshot{
			RegistryKeys: make([]string, 0),
			Files:        make([]string, 0),
		}

		// Cross-platform file scanning
		scanDirs := getPlatformScanDirs()
		for _, dir := range scanDirs {
			if dir != "" {
				scanDirectory(dir, &snap.Files, 100000)
			}
		}

		// Windows Registry scanning (Simplified stub for cross-platform binary)
		if runtime.GOOS == "windows" {
			// In a production Go build, we would use conditional compilation (// +build windows)
			// to include the real registry scanning code provided in the proposal.
			// scanRegistry(registry.LOCAL_MACHINE, `SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`, &snap.RegistryKeys)
		}

		data, _ := json.MarshalIndent(snap, "", "  ")
		_ = ioutil.WriteFile(*targetFile, data, 0644)
		fmt.Println("SUCCESS_SCAN")

	} else if *mode == "delete" {
		// Read the log and execute deletion
		data, err := ioutil.ReadFile(*targetFile)
		if err != nil {
			fmt.Printf("ERROR: Failed to read log: %v\n", err)
			os.Exit(1)
		}

		var blg struct {
			RegAdded  []string `json:"reg_added"`
			FileAdded []string `json:"file_added"`
		}
		if err := json.Unmarshal(data, &blg); err != nil {
			fmt.Printf("ERROR: Failed to parse log: %v\n", err)
			os.Exit(1)
		}

		fmt.Println("EXECUTE_CLEAN")
		for _, file := range blg.FileAdded {
			fmt.Printf("Deleting: %s\n", file)
			// Actually remove them
			err := os.RemoveAll(file)
			if err != nil {
				fmt.Printf("Failed to delete %s: %v\n", file, err)
			}
		}
		fmt.Println("CLEAN_COMPLETE")
	}
}
