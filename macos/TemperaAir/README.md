# Tempera Air macOS app

This is a macOS 14+ SwiftUI client for the versioned `android-sim --json`
contract. It deliberately does not duplicate emulator state.

On an Apple Silicon Mac:

```bash
swift build -c release
TEMPERA_CLI=/absolute/path/to/android-sim swift run TemperaAir
```

The current UI is the management foundation. Low-latency GameController and
token-authenticated emulator gRPC integration remain gated on the custom engine
build and hardware validation.
