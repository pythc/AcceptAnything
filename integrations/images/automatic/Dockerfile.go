FROM golang:1.26-alpine
RUN go install gotest.tools/gotestsum@v1.13.0
