// facebox : largest face in each image, via Apple Vision (local, free).
//   facebox img1.png img2.png ...         -> one JSON line per image : {"file","x","y","w","h"} (normalised, origin top-left) or "face":null
//   facebox --text img1.png img2.png ...  -> one JSON line per image : {"file","n","area","text"} on-screen text found (fast recognition)
// Compiled by scripts/install.sh into tools/bin/facebox (swiftc -O).
import Foundation
import Vision
import AppKit

var args = Array(CommandLine.arguments.dropFirst())
let textMode = args.first == "--text"
if textMode { args.removeFirst() }

func esc(_ s: String) -> String {
    return s.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "\"", with: "\\\"")
}

for path in args {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { print("{\"file\":\"\(esc(path))\",\"face\":null}"); continue }
    if textMode {
        let req = VNRecognizeTextRequest()
        req.recognitionLevel = .accurate
        req.usesLanguageCorrection = false
        try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
        let obs = (req.results ?? []).filter { $0.confidence > 0.5 }
        let area = obs.reduce(0.0) { $0 + Double($1.boundingBox.width * $1.boundingBox.height) }
        let words = obs.compactMap { $0.topCandidates(1).first?.string }.joined(separator: " | ")
        print(String(format: "{\"file\":\"%@\",\"n\":%d,\"area\":%.4f,\"text\":\"%@\"}", esc(path), obs.count, area, esc(words)))
        continue
    }
    let req = VNDetectFaceRectanglesRequest()
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    let faces = (req.results ?? []).sorted { $0.boundingBox.width * $0.boundingBox.height > $1.boundingBox.width * $1.boundingBox.height }
    if let f = faces.first {
        let b = f.boundingBox
        print(String(format: "{\"file\":\"%@\",\"x\":%.4f,\"y\":%.4f,\"w\":%.4f,\"h\":%.4f}", esc(path), b.minX, 1 - b.maxY, b.width, b.height))
    } else { print("{\"file\":\"\(esc(path))\",\"face\":null}") }
}
