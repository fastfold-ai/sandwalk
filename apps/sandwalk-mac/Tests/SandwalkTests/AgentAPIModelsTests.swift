import Foundation
import XCTest
@testable import SandwalkCore

/// Matches `SandwalkAPIClient`'s plain `JSONDecoder()` (camelCase keys, no snake_case strategy).
final class AgentAPIModelsTests: XCTestCase {
    private let decoder = JSONDecoder()

    func testAgentModelDTODecodeRoundtrip() throws {
        let json = """
        {
          "id": "gpt-4o",
          "label": "GPT-4o",
          "description": "OpenAI flagship",
          "provider": "openai",
          "source": "cloud",
          "profileId": "openai_cloud",
          "enabled": true,
          "health": "ok"
        }
        """.data(using: .utf8)!

        let model = try decoder.decode(AgentModelDTO.self, from: json)
        XCTAssertEqual(model.id, "gpt-4o")
        XCTAssertEqual(model.label, "GPT-4o")
        XCTAssertEqual(model.description, "OpenAI flagship")
        XCTAssertEqual(model.provider, "openai")
        XCTAssertEqual(model.source, "cloud")
        XCTAssertEqual(model.profileId, "openai_cloud")
        XCTAssertTrue(model.enabled)
        XCTAssertEqual(model.health, "ok")

        let encoded = try JSONEncoder().encode(model)
        let again = try decoder.decode(AgentModelDTO.self, from: encoded)
        XCTAssertEqual(again, model)
    }

    func testToolCatalogDTODecode() throws {
        let json = """
        {
          "data": [
            {
              "id": "chem.search",
              "name": "chem.search",
              "category": "chem",
              "status": "ready",
              "description": "Search compounds",
              "requiresData": ["chembl"],
              "enabled": true
            }
          ],
          "count": 1,
          "categories": ["chem"]
        }
        """.data(using: .utf8)!

        let catalog = try decoder.decode(ToolCatalogDTO.self, from: json)
        XCTAssertEqual(catalog.count, 1)
        XCTAssertEqual(catalog.categories, ["chem"])
        XCTAssertEqual(catalog.data.count, 1)
        XCTAssertEqual(catalog.data[0].id, "chem.search")
        XCTAssertEqual(catalog.data[0].requiresData, ["chembl"])
        XCTAssertTrue(catalog.data[0].enabled)
    }

    func testDatasetSummaryDTODecodeRoundtrip() throws {
        let json = """
        {
          "id": "depmap",
          "description": "DepMap CRISPR screens",
          "status": "installed",
          "filesFound": 3,
          "filesExpected": 3,
          "sizeDisplay": "1.2 GB",
          "autoDownload": false,
          "path": "/tmp/depmap",
          "note": null
        }
        """.data(using: .utf8)!

        let dataset = try decoder.decode(DatasetSummaryDTO.self, from: json)
        XCTAssertEqual(dataset.id, "depmap")
        XCTAssertEqual(dataset.status, "installed")
        XCTAssertEqual(dataset.filesFound, 3)
        XCTAssertEqual(dataset.filesExpected, 3)
        XCTAssertEqual(dataset.sizeDisplay, "1.2 GB")
        XCTAssertEqual(dataset.autoDownload, false)
        XCTAssertEqual(dataset.path, "/tmp/depmap")
        XCTAssertNil(dataset.note)

        let encoded = try JSONEncoder().encode(dataset)
        let again = try decoder.decode(DatasetSummaryDTO.self, from: encoded)
        XCTAssertEqual(again, dataset)
    }
}
