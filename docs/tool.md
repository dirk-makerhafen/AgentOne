---
tools:
  - name: read
    type: python
    file: filesystem.py
    function: read

  - name: write
    type: python
    file: filesystem.py
    function: write

  - name: my-binary-tool
    type: shell
    command: ./bin/my-tool {path}
    description: "Process a file through a custom binary"
    parameters:
      path:
        type: string
        description: "Path to the file to process"

  - name: remote-api
    type: shell
    command: curl -X POST https://api.example.com/process -d '{input}'
    description: "Call external API"
    parameters:
      input:
        type: string
        description: "Input data"