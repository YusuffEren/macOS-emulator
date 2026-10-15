import Foundation

struct Envelope: Decodable {
    let schemaVersion: Int
    let requestId: String
    let status: String
    let data: JSONValue?
    let warnings: [String]
    let error: APIError?

    enum CodingKeys: String, CodingKey {
        case schemaVersion = "schema_version", requestId = "request_id", status, data, warnings, error
    }
}

struct APIError: Decodable, Error {
    let code: String
    let message: String
}

enum JSONValue: Decodable {
    case string(String), number(Double), bool(Bool), object([String: JSONValue]), array([JSONValue]), null

    init(from decoder: Decoder) throws {
        let box = try decoder.singleValueContainer()
        if box.decodeNil() { self = .null }
        else if let value = try? box.decode(Bool.self) { self = .bool(value) }
        else if let value = try? box.decode(Double.self) { self = .number(value) }
        else if let value = try? box.decode(String.self) { self = .string(value) }
        else if let value = try? box.decode([String: JSONValue].self) { self = .object(value) }
        else { self = .array(try box.decode([JSONValue].self)) }
    }
}

actor CLIClient {
    private var executable: URL {
        if let configured = ProcessInfo.processInfo.environment["TEMPERA_CLI"] {
            return URL(fileURLWithPath: configured)
        }
        if let bundled = Bundle.main.url(forResource: "android-sim", withExtension: nil, subdirectory: "bin") {
            return bundled
        }
        return URL(fileURLWithPath: "/usr/local/bin/android-sim")
    }

    func run(_ arguments: [String]) async throws -> Envelope {
        let process = Process()
        let output = Pipe()
        let errors = Pipe()
        process.executableURL = executable
        process.arguments = ["--json"] + arguments
        process.standardOutput = output
        process.standardError = errors
        try process.run()
        process.waitUntilExit()
        let data = output.fileHandleForReading.readDataToEndOfFile()
        guard !data.isEmpty else {
            let detail = String(data: errors.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? "No output"
            throw APIError(code: "cli_unavailable", message: detail)
        }
        let envelope = try JSONDecoder().decode(Envelope.self, from: data)
        if let error = envelope.error { throw error }
        return envelope
    }
}
