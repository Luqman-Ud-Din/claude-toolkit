package main

import "net/http"

func main() {
	http.HandleFunc("/orders", func(w http.ResponseWriter, r *http.Request) { w.Write([]byte("[]")) })
	http.ListenAndServe(":8080", nil)
}
