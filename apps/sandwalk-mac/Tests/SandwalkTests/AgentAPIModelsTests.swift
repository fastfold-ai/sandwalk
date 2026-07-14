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
        XCTAssertNil(model.backend)
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
              "enabled": true,
              "tier": "core"
            },
            {
              "id": "chem.extra",
              "name": "chem.extra",
              "category": "chem",
              "status": "ready",
              "description": "Extra tool",
              "requiresData": null,
              "enabled": false
            }
          ],
          "count": 2,
          "categories": ["chem"]
        }
        """.data(using: .utf8)!

        let catalog = try decoder.decode(ToolCatalogDTO.self, from: json)
        XCTAssertEqual(catalog.count, 2)
        XCTAssertEqual(catalog.categories, ["chem"])
        XCTAssertEqual(catalog.data.count, 2)
        XCTAssertEqual(catalog.data[0].id, "chem.search")
        XCTAssertEqual(catalog.data[0].requiresData, ["chembl"])
        XCTAssertTrue(catalog.data[0].enabled)
        XCTAssertEqual(catalog.data[0].tier, "core")
        XCTAssertTrue(catalog.data[0].isCore)
        XCTAssertNil(catalog.data[1].tier)
        XCTAssertFalse(catalog.data[1].isCore)
    }

    func testSpecialistDTODecodeToolNames() throws {
        let json = """
        {
          "id": "sp_1",
          "name": "Fast",
          "slug": "fast",
          "description": null,
          "instructions": "Be brief",
          "color": "blue",
          "icon": "zap",
          "skillNames": ["fold"],
          "toolNames": ["chem.search", "run_python"],
          "mcpServerIds": [],
          "mcpCatalogIds": ["tamarind"],
          "enabled": true,
          "createdAt": "2026-01-01T00:00:00Z",
          "updatedAt": "2026-01-02T00:00:00Z"
        }
        """.data(using: .utf8)!

        let specialist = try decoder.decode(SpecialistDTO.self, from: json)
        XCTAssertEqual(specialist.id, "sp_1")
        XCTAssertEqual(specialist.toolNames, ["chem.search", "run_python"])
        XCTAssertEqual(specialist.skillNames, ["fold"])
        XCTAssertEqual(specialist.mcpCatalogIds, ["tamarind"])
        XCTAssertTrue(specialist.enabled)
    }

    func testSpecialistDTODecodeMissingToolNamesDefaultsEmpty() throws {
        let json = """
        {
          "id": "sp_2",
          "name": "Legacy",
          "slug": "legacy",
          "color": "ink",
          "icon": "agent",
          "skillNames": [],
          "mcpServerIds": [],
          "mcpCatalogIds": [],
          "enabled": true
        }
        """.data(using: .utf8)!

        let specialist = try decoder.decode(SpecialistDTO.self, from: json)
        XCTAssertEqual(specialist.toolNames, [])
        XCTAssertEqual(specialist.skillNames, [])
    }

    func testPromptBudgetResponseDTODecode() throws {
        let json = """
        {
          "totalTokens": 4200,
          "totalChars": 16800,
          "tokenizer": "chars/4",
          "toolMode": "ptc",
          "provider": "anthropic",
          "model": "claude-sonnet-4-5",
          "specialistId": "sp_1",
          "specialistName": "Fast",
          "toolCounts": {
            "domain": 40,
            "mcp": 5,
            "deepagents": 8,
            "total": 53,
            "openaiCap": 128
          },
          "buckets": [
            {
              "id": "system",
              "label": "System",
              "tokens": 3000,
              "chars": 12000,
              "count": null,
              "children": [
                {
                  "id": "skills",
                  "label": "Skills",
                  "tokens": 500,
                  "chars": 2000,
                  "count": 2,
                  "children": []
                }
              ]
            }
          ],
          "warnings": ["Near cap"],
          "sampleQuery": "Hello"
        }
        """.data(using: .utf8)!

        let budget = try decoder.decode(PromptBudgetResponseDTO.self, from: json)
        XCTAssertEqual(budget.totalTokens, 4200)
        XCTAssertEqual(budget.toolCounts.total, 53)
        XCTAssertEqual(budget.toolCounts.openaiCap, 128)
        XCTAssertEqual(budget.buckets.count, 1)
        XCTAssertEqual(budget.buckets[0].children.count, 1)
        XCTAssertEqual(budget.buckets[0].children[0].count, 2)
        XCTAssertEqual(budget.warnings, ["Near cap"])
        XCTAssertEqual(budget.specialistName, "Fast")
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

    func testRuntimeSettingsDTODecode() throws {
        let json = """
        {
          "provider": "anthropic",
          "model": "claude-sonnet-4-5-20250929",
          "openaiBaseUrl": null,
          "agentProfile": "research",
          "toolMode": "ptc",
          "recursionLimit": 120,
          "maxSdkTurns": 30,
          "groupToolTraces": true,
          "toolTraceDetailLimit": 1,
          "backgroundWatchTimeoutS": 7200,
          "interruptDrainTimeoutS": 10,
          "parallelMaxThreads": 5,
          "toolHealthEnabled": true,
          "toolHealthFailThreshold": 2,
          "toolHealthSuppressSeconds": 900
        }
        """.data(using: .utf8)!

        let settings = try decoder.decode(RuntimeSettingsDTO.self, from: json)
        XCTAssertEqual(settings.provider, "anthropic")
        XCTAssertEqual(settings.toolMode, "ptc")
        XCTAssertEqual(settings.recursionLimit, 120)
        XCTAssertEqual(settings.parallelMaxThreads, 5)
        XCTAssertTrue(settings.groupToolTraces)
        XCTAssertTrue(settings.toolHealthEnabled)
        XCTAssertNil(settings.openaiBaseUrl)
    }
}
