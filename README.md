# My Coding Studio Web — Python Browser Runtime

Base: Consolidated V2.

Added Python `.py` execution in the browser using Pyodide WebAssembly in a module Web Worker. JavaScript, Google Drive, editor, import/export, snapshots, output panel, AI endpoint and optional cloud-runner fallback are preserved.

Python first run downloads the Pyodide runtime from the official recommended jsDelivr CDN path, so internet is required for the first load; the browser may cache it afterward. Browser/WASM networking has browser/CORS/socket limitations.
