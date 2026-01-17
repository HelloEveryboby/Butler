package main

import (
	"fmt"
	"os"
	"strings"
)

func main() {
	if len(os.Args) > 1 {
		message := strings.Join(os.Args[1:], " ")
		fmt.Printf("Hello, %s from Go!\n", message)
	} else {
		fmt.Println("Hello World from Go!")
	}
}
