import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : Tender Agent
// Nodes   : 22  |  Connections: 22
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// Webhook                            webhook                    
// RespondToWebhook                   respondToWebhook           
// RespondToWebhook1                  respondToWebhook           
// RespondToWebhook2                  respondToWebhook           
// CheckInput                         if                         
// NormaliseInputs                    set                        
// SanitizePerplexityOutput           set                        
// PerplexityHttpRequest1             httpRequest                [creds]
// PrepareResultForStorage            set                        
// AppendRowInEchoStatusSheet         googleSheets               [creds]
// SecretCheck                        if                         
// QcPromptPrep                       set                        
// PerplexityQcCritic                 httpRequest                [creds]
// TidyQcOutputs                      set                        
// Merge                              merge                      
// _1RawTextIn                        set                        
// _2SplitThink                       set                        
// _3StripFences                      set                        
// _4SliceJson                        set                        
// _5ParseJson                        set                        
// InsertRow                          dataTable                  
// CreateClean1ForStorage             set                        
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// Webhook
//    → SecretCheck
//      → CheckInput
//        → NormaliseInputs
//          → PerplexityHttpRequest1
//            → QcPromptPrep
//              → PerplexityQcCritic
//                → TidyQcOutputs
//                  → Merge.in(1)
//                    → CreateClean1ForStorage
//                      → PrepareResultForStorage
//                        → RespondToWebhook
//                        → InsertRow
//                        → AppendRowInEchoStatusSheet
//            → _1RawTextIn
//              → _2SplitThink
//                → _3StripFences
//                  → _4SliceJson
//                    → _5ParseJson
//                      → SanitizePerplexityOutput
//                        → Merge (↩ loop)
//       .out(1) → RespondToWebhook2
//     .out(1) → RespondToWebhook1
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: "as0bBnphpdYHvLs6",
    name: "Tender Agent",
    active: true,
    settings: {executionOrder:"v1"}
})
export class TenderAgentWorkflow {

    // =====================================================================
// CONFIGURATION DES NOEUDS
// =====================================================================

    @node({
        name: "Webhook",
        type: "n8n-nodes-base.webhook",
        version: 2.1,
        position: [320, 16]
    })
    Webhook = {
        "httpMethod": "POST",
        "path": "tender_agent",
        "responseMode": "responseNode",
        "options": {}
    };

    @node({
        name: "Respond to Webhook",
        type: "n8n-nodes-base.respondToWebhook",
        version: 1.4,
        position: [3456, 16]
    })
    RespondToWebhook = {
        "respondWith": "allIncomingItems",
        "options": {
            "responseCode": 200,
            "responseHeaders": {
                "entries": [
                    {
                        "name": "Content-Type",
                        "value": "application/json"
                    }
                ]
            }
        }
    };

    @node({
        name: "Respond to Webhook1",
        type: "n8n-nodes-base.respondToWebhook",
        version: 1.4,
        position: [768, 112]
    })
    RespondToWebhook1 = {
        "respondWith": "json",
        "responseBody": "{\n  \"error\":\"Unauthorized - secret fail\"\n}",
        "options": {}
    };

    @node({
        name: "Respond to Webhook2",
        type: "n8n-nodes-base.respondToWebhook",
        version: 1.4,
        position: [992, -80]
    })
    RespondToWebhook2 = {
        "respondWith": "json",
        "responseBody": "={ \"status\": \"error\", \"message\": \"taxonomy_question missing in payload\" }\n",
        "options": {}
    };

    @node({
        name: "Check Input",
        type: "n8n-nodes-base.if",
        version: 2.2,
        position: [768, -80]
    })
    CheckInput = {
        "conditions": {
            "options": {
                "caseSensitive": true,
                "leftValue": "",
                "typeValidation": "strict",
                "version": 2
            },
            "conditions": [
                {
                    "id": "fa33d200-1df7-4a04-8a19-bd5027fdffc4",
                    "leftValue": "={{ $json.body.tender_question }}",
                    "rightValue": "",
                    "operator": {
                        "type": "string",
                        "operation": "notEmpty",
                        "singleValue": true
                    }
                }
            ],
            "combinator": "and"
        },
        "options": {}
    };

    @node({
        name: "Normalise Inputs",
        type: "n8n-nodes-base.set",
        version: 3.4,
        position: [992, -272]
    })
    NormaliseInputs = {
        "assignments": {
            "assignments": [
                {
                    "id": "4c867557-bf0e-4235-ba7d-830c1c7505a6",
                    "name": "tender_question",
                    "value": "={{$json[\"body\"]?.[\"tender_question\"] || \"\"}}",
                    "type": "string"
                },
                {
                    "id": "a8679b5f-e177-4530-a20b-c8af66e02eea",
                    "name": "authority_name",
                    "value": "={{$json[\"body\"]?.[\"authority_name\"] || \"\"}}",
                    "type": "string"
                },
                {
                    "id": "12e034c4-7182-4e34-874a-d8a4fd02553c",
                    "name": "question_id",
                    "value": "={{$json[\"body\"]?.[\"question_id\"] || \"\"}}",
                    "type": "string"
                },
                {
                    "id": "8300e1f6-7cbd-4eef-bf9e-89746d3b2872",
                    "name": "evidence_input",
                    "value": "={{$json[\"body\"]?.[\"evidence_input\"] || \"\"}}",
                    "type": "string"
                },
                {
                    "id": "f2f8450d-3af5-4c9b-b988-cf54bb9ee87b",
                    "name": "model_name",
                    "value": "={{ (typeof $json[\"body\"]?.[\"model_name\"] !== \"undefined\" && $json[\"body\"][\"model_name\"]) ? $json[\"body\"][\"model_name\"] : \"sonar\" }}",
                    "type": "string"
                },
                {
                    "id": "a293c84f-4458-47d8-bf2b-475674fb7be5",
                    "name": "temperature",
                    "value": "={{ typeof $json[\"body\"]?.[\"temperature\"] !== \"undefined\" ? Number($json[\"body\"][\"temperature\"]) : 0 }}",
                    "type": "number"
                },
                {
                    "id": "1f2bf73c-2b96-4e9b-80b0-36b1185ed8e1",
                    "name": "max_tokens",
                    "value": "={{ typeof $json[\"body\"]?.[\"max_tokens\"] !== \"undefined\" ? Number($json[\"body\"][\"max_tokens\"]) : 4000 }}",
                    "type": "number"
                },
                {
                    "id": "4f9f171c-5088-4882-96ca-36335122260a",
                    "name": "query_depth",
                    "value": "={{ typeof $json[\"body\"]?.[\"query_depth\"] !== \"undefined\" ? Number($json[\"body\"][\"query_depth\"]) : 3 }}",
                    "type": "number"
                },
                {
                    "id": "03d82865-f9f7-4b5a-9e5c-ac4296d804e9",
                    "name": "global_context",
                    "value": "={{$json[\"body\"]?.[\"global_context\"] || \"\"}}",
                    "type": "string"
                },
                {
                    "id": "8eda6a2c-f669-414a-82d3-87b758973e39",
                    "name": "extra_context",
                    "value": "={{ (() => { const mode = $json[\"body\"]?.[\"MODE\"] || \"TENDER_RESPONSE\"; const extra = $json[\"body\"]?.[\"extra_context\"] || \"\"; if (/^\\s*MODE\\s*:/im.test(extra)) return extra; return `MODE: ${mode}\\n\\n${extra}`.trim(); })() }}",
                    "type": "string"
                },
                {
                    "id": "b963df5f-7fe3-4ad3-8b95-78dde669a573",
                    "name": "qc_critic_prompt",
                    "value": "={{ $json[\"body\"]?.[\"qc_critic_prompt\"] || \"\" }}",
                    "type": "string"
                },
                {
                    "id": "303a8518-3613-4e51-917c-924756ecd48c",
                    "name": "prompt_text",
                    "value": "={{ $json.body.prompt_text }}",
                    "type": "string"
                },
                {
                    "id": "id-new-mode",
                    "name": "MODE",
                    "value": "={{ $json[\"body\"]?.[\"MODE\"] || \"TENDER_RESPONSE\" }}",
                    "type": "string"
                }
            ]
        },
        "options": {}
    };

    @node({
        name: "Sanitize Perplexity Output",
        type: "n8n-nodes-base.set",
        version: 3.4,
        position: [2560, -368]
    })
    SanitizePerplexityOutput = {
        "assignments": {
            "assignments": [
                {
                    "id": "eb9e43d0-cb28-4cb6-ad06-5b4c4c692179",
                    "name": "timestamp",
                    "value": "={{ new Date().toISOString() }}",
                    "type": "string"
                },
                {
                    "id": "051a1cd4-d612-4cd1-be70-de2cf95a0062",
                    "name": "model",
                    "value": "={{ $json.body.model }}",
                    "type": "string"
                },
                {
                    "id": "94fd829b-3650-4d82-a3da-b5ace43bb42d",
                    "name": "total_tokens",
                    "value": "={{ $json.body.usage.total_tokens }}",
                    "type": "number"
                },
                {
                    "id": "b9744d86-fb79-46f8-9308-2e5e5ca8a226",
                    "name": "cost_usd",
                    "value": "={{ $json.body.usage.cost.total_cost }}",
                    "type": "number"
                },
                {
                    "id": "7854b209-c467-493f-97bf-e40af54fda02",
                    "name": "citations",
                    "value": "={{ $json[\"body\"][\"citations\"] }}",
                    "type": "object"
                },
                {
                    "id": "e0be0962-eaf6-4675-9b5c-f0d29446f219",
                    "name": "search_results",
                    "value": "={{ $json.body.search_results }}",
                    "type": "object"
                },
                {
                    "id": "c8561e74-ffed-4cb0-a570-bdaf2e063e06",
                    "name": "llm_output_raw",
                    "value": "={{ $json.body.choices[0].message.content }}",
                    "type": "string"
                },
                {
                    "id": "7c153f91-0aa9-4e8d-8116-3803d1b12a8d",
                    "name": "llm_output_parsed",
                    "value": "={{ null }}",
                    "type": "string"
                },
                {
                    "id": "9ebadc48-46f7-44e8-aa9a-95181703c617",
                    "name": "llm_output_clean",
                    "value": "={{ $json.llm_output_clean || $json.json_slice || \"\" }}",
                    "type": "string"
                },
                {
                    "id": "ef4b0026-4e0d-4a64-a8b0-a049a176f2d0",
                    "name": "think_block",
                    "value": "={{ $json.think_block || \"\" }}",
                    "type": "string"
                }
            ]
        },
        "options": {
            "ignoreConversionErrors": true
        }
    };

    @node({
        name: "Perplexity HTTP Request1",
        type: "n8n-nodes-base.httpRequest",
        version: 4.2,
        position: [1216, -272],
        credentials: {perplexityApi:{id:"SkSOGLP98gXnuOBu",name:"Perplexity account"}}
    })
    PerplexityHttpRequest1 = {
        "method": "POST",
        "url": "https://api.perplexity.ai/chat/completions",
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "perplexityApi",
        "sendHeaders": true,
        "headerParameters": {
            "parameters": [
                {
                    "name": "Content-Type",
                    "value": "application/json"
                }
            ]
        },
        "sendBody": true,
        "bodyParameters": {
            "parameters": [
                {
                    "name": "model",
                    "value": "={{ $json.model_name || $json.body?.model_name || \"sonar-deep-research\" }}\n"
                },
                {
                    "name": "max_tokens",
                    "value": "={{ $json.max_tokens ?? $json.body?.max_tokens ?? 2500 }}\n"
                },
                {
                    "name": "temperature",
                    "value": "={{ $json.temperature ?? $json.body?.temperature ?? 0.15 }}\n"
                },
                {
                    "name": "stream",
                    "value": "false"
                },
                {
                    "name": "messages",
                    "value": "={{[\n  {\n    role: 'system',\n    content: ($json.prompt_text)\n  },\n  { role: 'user', \n    content:\n      'Global tender context (sector-level guidance only):\\n' +\n      ($json.global_context) +\n\n      '\\n\\nTender question:\\n' +\n      ($json.tender_question) +\n\n      '\\n\\nAuthority name (may be empty):\\n' +\n      ($json.authority_name) +\n\n      '\\n\\nTender metadata:\\n' +\n      'tender_id=' + ($json.tender_id) +\n      '; question_id=' + ($json.question_id) +\n\n      '\\\\n\\\\nRun config (for meta fields only):\\\\n' +\n      'model_name=' + ($json.model_name) +\n      '; temperature=' + ($json.temperature) +\n      '; max_tokens=' + ($json.max_tokens) +\n\n      '\\n\\nEvidence input (primary factual source):\\n' +\n      ($json.evidence_input) +\n\n      '\\n\\nExtra context and QC instructions:\\n' +\n      ($json.extra_context)\n}\n]}}"
                },
                {
                    "name": "use_context",
                    "value": "true"
                },
                {
                    "name": "taxonomy_url",
                    "value": "\"https://raw.githubusercontent.com/Steve-Loncar/echo_test/main/taxonomy_normalized_cleaned.xlsx\""
                }
            ]
        },
        "options": {
            "response": {
                "response": {
                    "fullResponse": true,
                    "responseFormat": "json"
                }
            },
            "timeout": "=600000"
        }
    };

    @node({
        name: "Prepare result for storage",
        type: "n8n-nodes-base.set",
        version: 3.4,
        position: [3232, -272]
    })
    PrepareResultForStorage = {
        "assignments": {
            "assignments": [
                {
                    "id": "2ea4e6c2-2a92-4155-8445-506c65cf2f07",
                    "name": "store.run_id",
                    "value": "={{ $('Webhook').item.json.body.run_id }}",
                    "type": "string"
                },
                {
                    "id": "f6c16f9b-8488-4e0a-ae88-f6316e207807",
                    "name": "store.status",
                    "value": "completed",
                    "type": "string"
                },
                {
                    "id": "f8f8ed78-b4f9-4d53-bb82-9216e870deff",
                    "name": "store.timestamp_utc",
                    "value": "={{$now}}",
                    "type": "string"
                },
                {
                    "id": "9af85be4-8128-4c9c-9f63-c0d343273079",
                    "name": "store.env_mode",
                    "value": "={{ $('Check Input').item.json.body.env_mode }}",
                    "type": "string"
                },
                {
                    "id": "def93e21-4b45-495a-9654-1bd66c516867",
                    "name": "store.model_name",
                    "value": "={{$json[\"model\"]}}",
                    "type": "string"
                },
                {
                    "id": "ea6996cd-1cf9-4dc0-8d2d-45c759b0943a",
                    "name": "store.result_raw_1",
                    "value": "={{\n  (() => {\n    const s = $json.llm_output_clean1 || '';\n    return s.length > 49000 ? s.substring(0, 49000) : s;\n  })()\n}}\n\n",
                    "type": "string"
                },
                {
                    "id": "a862eb1d-a1e6-4b69-84de-fc58c882816d",
                    "name": "store.result_raw_2",
                    "value": "={{\n  (() => {\n    const s = $json.llm_output_clean1 || '';\n    return s.length > 98000 ? s.substring(49000, 98000) : (s.length > 49000 ? s.substring(49000) : '');\n  })()\n}}",
                    "type": "string"
                },
                {
                    "id": "333e8db3-070f-4e97-9cc3-e4076bd5b1d8",
                    "name": "store.result_raw_3",
                    "value": "={{\n  (() => {\n    const s = $json.llm_output_clean1 || '';\n    return s.length > 98000 ? s.substring(98000, 140000) : (s.length > 98000 ? s.substring(98000) : '');\n  })()\n}}",
                    "type": "string"
                },
                {
                    "id": "452b3681-ed84-469c-a6c8-23a6f2e3ae37",
                    "name": "qc_issues_detected",
                    "value": "={{ $json.qc_issues_detected || '[]' }}",
                    "type": "string"
                },
                {
                    "id": "b0b22a47-b99d-438c-9503-1733ddf9b5c4",
                    "name": "qc_issue_summaries",
                    "value": "={{ $json.qc_issue_summaries || '[]' }}",
                    "type": "string"
                },
                {
                    "id": "a5bd0d6f-af11-4439-9563-f69543c0b4f3",
                    "name": "qc_rerun_recommended",
                    "value": "={{ $json.qc_rerun_recommended || false }}",
                    "type": "boolean"
                },
                {
                    "id": "3e1fa924-5585-4a5e-b2e8-960f82691b23",
                    "name": "qc_suggested_model",
                    "value": "={{ $json.qc_suggested_model || '' }}",
                    "type": "string"
                },
                {
                    "id": "3c58c6fb-82a6-4058-9d2e-f8f717bf4f2b",
                    "name": "qc_suggested_temperature",
                    "value": "={{ $json.qc_suggested_temperature !== undefined && $json.qc_suggested_temperature !== null\n    ? $json.qc_suggested_temperature\n    : null }}",
                    "type": "number"
                },
                {
                    "id": "36eeca21-2f33-4177-bb8f-e62af7ee49fb",
                    "name": "qc_suggested_max_tokens",
                    "value": "={{ $json.qc_suggested_max_tokens !== undefined && $json.qc_suggested_max_tokens !== null\n    ? $json.qc_suggested_max_tokens\n    : null }}",
                    "type": "number"
                },
                {
                    "id": "b13716a2-f83b-44ee-ae7c-f35f3270b945",
                    "name": "qc_suggested_extra_context_append",
                    "value": "={{ $json.qc_suggested_extra_context_append || '' }}",
                    "type": "string"
                },
                {
                    "id": "bb4db380-84c0-40f9-8900-7afe08138b7d",
                    "name": "qc_recommended_actions",
                    "value": "={{ $json.qc_recommended_actions || '[]' }}",
                    "type": "string"
                },
                {
                    "id": "5311f8c5-5d66-490d-bde5-33ca26f736dd",
                    "name": "qc_strengths_summary",
                    "value": "={{ $json.qc_strengths_summary || '[]' }}",
                    "type": "string"
                },
                {
                    "id": "612532af-763c-4494-bd6f-777ae9b2482c",
                    "name": "qc_optional_improvements",
                    "value": "={{ $json.qc_optional_improvements || '[]' }}",
                    "type": "string"
                },
                {
                    "id": "4d815539-7812-4285-947b-9fa454a75f53",
                    "name": "store.total_tokens",
                    "value": "={{ $json.total_tokens }}",
                    "type": "number"
                },
                {
                    "id": "a61df8b2-3f7b-4098-8954-e5d6775fc01b",
                    "name": "store.cost_usd",
                    "value": "={{ $json.cost_usd }}",
                    "type": "number"
                },
                {
                    "id": "92c295ff-6046-40bb-8b15-09a80e7aa388",
                    "name": "store.citations",
                    "value": "={{ $json.citations }}",
                    "type": "array"
                }
            ]
        },
        "includeOtherFields": true,
        "options": {}
    };

    @node({
        name: "Append row in ECHO STATUS sheet",
        type: "n8n-nodes-base.googleSheets",
        version: 4.7,
        position: [3456, -368],
        credentials: {googleSheetsOAuth2Api:{id:"qT2xaECAtZUmEzfn",name:"Google Sheets account 2"}}
    })
    AppendRowInEchoStatusSheet = {
        "operation": "append",
        "documentId": {
            "__rl": true,
            "value": "1LClC3bnR0ayQfy_m86aTFsTwCfxmF-NeamWZLiM6SXU",
            "mode": "list",
            "cachedResultName": "tender_agent_database",
            "cachedResultUrl": "https://docs.google.com/spreadsheets/d/1LClC3bnR0ayQfy_m86aTFsTwCfxmF-NeamWZLiM6SXU/edit?usp=drivesdk"
        },
        "sheetName": {
            "__rl": true,
            "value": "Tender_Results",
            "mode": "name"
        },
        "columns": {
            "mappingMode": "defineBelow",
            "value": {
                "timestamp_utc": "={{ $json.store.timestamp_utc }}",
                "total_tokens": "={{ $json.total_tokens }}",
                "cost_usd": "={{ $json.cost_usd }}",
                "citations": "={{ $json.store.citations }}",
                "model_name": "={{ $json.model }}",
                "run_id": "={{ $json.store.run_id }}",
                "status": "={{ $json.store.status }}",
                "env_mode": "={{ $json.store.env_mode }}",
                "qc_issues_detected": "={{ $json.qc_issues_detected }}",
                "qc_issue_summaries": "={{ $json.qc_issue_summaries }}",
                "qc_rerun_recommended": "={{ $json.qc_rerun_recommended }}",
                "qc_suggested_model": "={{ $json.qc_suggested_model }}",
                "qc_suggested_temperature": "={{ $json.qc_suggested_temperature }}",
                "qc_suggested_max_tokens": "={{ $json.qc_suggested_max_tokens }}",
                "qc_suggested_extra_context_append": "={{ $json.qc_suggested_extra_context_append }}",
                "qc_recommended_actions": "={{ $json.qc_recommended_actions }}",
                "qc_strengths_summary": "={{ $json.qc_strengths_summary }}",
                "qc_optional_improvements": "={{ $json.qc_optional_improvements }}"
            },
            "matchingColumns": [],
            "schema": [
                {
                    "id": "run_id",
                    "displayName": "run_id",
                    "required": false,
                    "defaultMatch": false,
                    "display": true,
                    "type": "string",
                    "canBeUsedToMatch": true
                },
                {
                    "id": "status",
                    "displayName": "status",
                    "required": false,
                    "defaultMatch": false,
                    "display": true,
                    "type": "string",
                    "canBeUsedToMatch": true
                },
                {
                    "id": "timestamp_utc",
                    "displayName": "timestamp_utc",
                    "required": false,
                    "defaultMatch": false,
                    "display": true,
                    "type": "string",
                    "canBeUsedToMatch": true
                },
                {
                    "id": "total_tokens",
                    "displayName": "total_tokens",
                    "required": false,
                    "defaultMatch": false,
                    "display": true,
                    "type": "string",
                    "canBeUsedToMatch": true
                },
                {
                    "id": "cost_usd",
                    "displayName": "cost_usd",
                    "required": false,
                    "defaultMatch": false,
                    "display": true,
                    "type": "string",
                    "canBeUsedToMatch": true
                },
                {
                    "id": "citations",
                    "displayName": "citations",
                    "required": false,
                    "defaultMatch": false,
                    "display": true,
                    "type": "string",
                    "canBeUsedToMatch": true
                },
                {
                    "id": "env_mode",
                    "displayName": "env_mode",
                    "required": false,
                    "defaultMatch": false,
                    "display": true,
                    "type": "string",
                    "canBeUsedToMatch": true
                },
                {
                    "id": "model_name",
                    "displayName": "model_name",
                    "required": false,
                    "defaultMatch": false,
                    "display": true,
                    "type": "string",
                    "canBeUsedToMatch": true
                },
                {
                    "id": "qc_issues_detected",
                    "displayName": "qc_issues_detected",
                    "required": false,
                    "defaultMatch": false,
                    "display": true,
                    "type": "string",
                    "canBeUsedToMatch": true
                },
                {
                    "id": "qc_issue_summaries",
                    "displayName": "qc_issue_summaries",
                    "required": false,
                    "defaultMatch": false,
                    "display": true,
                    "type": "string",
                    "canBeUsedToMatch": true
                },
                {
                    "id": "qc_rerun_recommended",
                    "displayName": "qc_rerun_recommended",
                    "required": false,
                    "defaultMatch": false,
                    "display": true,
                    "type": "string",
                    "canBeUsedToMatch": true
                },
                {
                    "id": "qc_suggested_model",
                    "displayName": "qc_suggested_model",
                    "required": false,
                    "defaultMatch": false,
                    "display": true,
                    "type": "string",
                    "canBeUsedToMatch": true
                },
                {
                    "id": "qc_suggested_temperature",
                    "displayName": "qc_suggested_temperature",
                    "required": false,
                    "defaultMatch": false,
                    "display": true,
                    "type": "string",
                    "canBeUsedToMatch": true
                },
                {
                    "id": "qc_suggested_max_tokens",
                    "displayName": "qc_suggested_max_tokens",
                    "required": false,
                    "defaultMatch": false,
                    "display": true,
                    "type": "string",
                    "canBeUsedToMatch": true
                },
                {
                    "id": "qc_suggested_extra_context_append",
                    "displayName": "qc_suggested_extra_context_append",
                    "required": false,
                    "defaultMatch": false,
                    "display": true,
                    "type": "string",
                    "canBeUsedToMatch": true
                },
                {
                    "id": "qc_recommended_actions",
                    "displayName": "qc_recommended_actions",
                    "required": false,
                    "defaultMatch": false,
                    "display": true,
                    "type": "string",
                    "canBeUsedToMatch": true
                },
                {
                    "id": "qc_strengths_summary",
                    "displayName": "qc_strengths_summary",
                    "required": false,
                    "defaultMatch": false,
                    "display": true,
                    "type": "string",
                    "canBeUsedToMatch": true,
                    "removed": false
                },
                {
                    "id": "qc_optional_improvements",
                    "displayName": "qc_optional_improvements",
                    "required": false,
                    "defaultMatch": false,
                    "display": true,
                    "type": "string",
                    "canBeUsedToMatch": true,
                    "removed": false
                }
            ],
            "attemptToConvertTypes": false,
            "convertFieldsToString": false
        },
        "options": {}
    };

    @node({
        name: "Secret check",
        type: "n8n-nodes-base.if",
        version: 2.2,
        position: [544, 16]
    })
    SecretCheck = {
        "conditions": {
            "options": {
                "caseSensitive": true,
                "leftValue": "",
                "typeValidation": "strict",
                "version": 2
            },
            "conditions": [
                {
                    "id": "ab0403f9-4175-421b-894f-68425fcf97f6",
                    "leftValue": "={{ $json.headers['x-webhook-secret'] }}",
                    "rightValue": "WIBBLE",
                    "operator": {
                        "type": "string",
                        "operation": "equals",
                        "name": "filter.operator.equals"
                    }
                }
            ],
            "combinator": "and"
        },
        "options": {}
    };

    @node({
        name: "QC Prompt Prep",
        type: "n8n-nodes-base.set",
        version: 3.4,
        position: [2112, -176]
    })
    QcPromptPrep = {
        "assignments": {
            "assignments": [
                {
                    "id": "c93d8537-4f49-426b-9ba7-270adc3ad682",
                    "name": "analysis_json_raw",
                    "value": "={{ 'Tender question:\\n' + ($('Normalise Inputs').item.json.tender_question || '') + '\\n\\nAuthority name (may be empty):\\n' + ($('Normalise Inputs').item.json.authority_name || '') + '\\n\\nMODE / extra_context (may influence evidence rules):\\n' + ($('Normalise Inputs').item.json.extra_context || '') + '\\n\\n---\\n\\nCORE OUTPUT JSON (to QC):\\n' + ($json.body.choices[0].message.content || '') }}",
                    "type": "string"
                },
                {
                    "id": "1a074a8f-476b-4047-98f6-89b017fe4724",
                    "name": "prompt_qc_critic",
                    "value": "={{ $('Check Input').item.json.body.qc_critic_prompt || '' }}\n",
                    "type": "string"
                }
            ]
        },
        "includeOtherFields": true,
        "options": {}
    };

    @node({
        name: "Perplexity QC Critic",
        type: "n8n-nodes-base.httpRequest",
        version: 4.2,
        position: [2336, -176],
        credentials: {perplexityApi:{id:"SkSOGLP98gXnuOBu",name:"Perplexity account"}}
    })
    PerplexityQcCritic = {
        "method": "POST",
        "url": "https://api.perplexity.ai/chat/completions",
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "perplexityApi",
        "sendHeaders": true,
        "headerParameters": {
            "parameters": [
                {
                    "name": "Content-Type",
                    "value": "application/json"
                }
            ]
        },
        "sendBody": true,
        "bodyParameters": {
            "parameters": [
                {
                    "name": "messages",
                    "value": "={{[\n\n{ \nrole: 'system', \ncontent: $json.prompt_qc_critic \n},\n\n\n{ \nrole: 'user', \ncontent: $json.analysis_json_raw,\nrun_metadata: {\nmodel_name: $json.body.model,\nMODE: $('Normalise Inputs').item.json.MODE,\nextra_context: $('Normalise Inputs').item.json.extra_context,\ntemperature: $('Normalise Inputs').item.json.temperature,\nmax_tokens: $('Normalise Inputs').item.json.max_tokens\n}\n}  \n]}}"
                },
                {
                    "name": "model",
                    "value": "sonar-pro"
                },
                {
                    "name": "max_tokens",
                    "value": "3000"
                },
                {
                    "name": "temperature",
                    "value": "0.1"
                },
                {
                    "name": "stream",
                    "value": "false"
                },
                {
                    "name": "use_context",
                    "value": "true"
                },
                {}
            ]
        },
        "options": {
            "response": {
                "response": {
                    "fullResponse": true,
                    "responseFormat": "json"
                }
            },
            "timeout": "=60000"
        }
    };

    @node({
        name: "Tidy QC outputs",
        type: "n8n-nodes-base.set",
        version: 3.4,
        position: [2560, -176]
    })
    TidyQcOutputs = {
        "assignments": {
            "assignments": [
                {
                    "id": "e6b287b7-6895-4bfa-b45c-3624c19e531e",
                    "name": "qc_issues_detected",
                    "value": "={{   (() => {     const raw = $json.body.choices[0].message.content || \"\";     const cleaned = raw       .replace(/```json\\s*([\\s\\S]*?)```/i, '$1')       .replace(/```\\s*([\\s\\S]*?)```/i, '$1')       .trim();     const qc = JSON.parse(cleaned);     return JSON.stringify(qc.issues_detected || []);   })() }}",
                    "type": "string"
                },
                {
                    "id": "29b7ab5a-fa85-4712-96ea-9371422e270b",
                    "name": "qc_issue_summaries",
                    "value": "={{   (() => {     const raw = $json.body.choices[0].message.content || \"\";     const cleaned = raw       .replace(/```json\\s*([\\s\\S]*?)```/i, '$1')       .replace(/```\\s*([\\s\\S]*?)```/i, '$1')       .trim();     const qc = JSON.parse(cleaned);     return JSON.stringify(qc.issue_summaries || []);   })() }}",
                    "type": "string"
                },
                {
                    "id": "f49c123c-0d55-45f4-b3aa-70cd98f6901e",
                    "name": "qc_rerun_recommended",
                    "value": "={{   (() => {     const raw = $json.body.choices[0].message.content || \"\";     const cleaned = raw       .replace(/```json\\s*([\\s\\S]*?)```/i, '$1')       .replace(/```\\s*([\\s\\S]*?)```/i, '$1')       .trim();     const qc = JSON.parse(cleaned);     return qc.rerun_recommended === true;   })() }}",
                    "type": "boolean"
                },
                {
                    "id": "1c29ac26-6ea5-46a2-a89e-e0eac66905f1",
                    "name": "qc_suggested_model",
                    "value": "={{   (() => {     const raw = $json.body.choices[0].message.content || \"\";     const cleaned = raw       .replace(/```json\\s*([\\s\\S]*?)```/i, '$1')       .replace(/```\\s*([\\s\\S]*?)```/i, '$1')       .trim();     const qc = JSON.parse(cleaned);     return qc.suggested_model || '';   })() }}",
                    "type": "string"
                },
                {
                    "id": "e78bc3b2-4f67-4763-8c6c-8309f9c263dc",
                    "name": "qc_suggested_temperature",
                    "value": "={{   (() => {     const raw = $json.body.choices[0].message.content || \"\";     const cleaned = raw       .replace(/```json\\s*([\\s\\S]*?)```/i, '$1')       .replace(/```\\s*([\\s\\S]*?)```/i, '$1')       .trim();     const qc = JSON.parse(cleaned);     const t = qc.suggested_temperature;     if (t === null || t === undefined) return null;     const clamped = Math.min(Math.max(t, 0.1), 0.35);     return clamped;   })() }}",
                    "type": "string"
                },
                {
                    "id": "ef4fc77f-6757-4702-bc75-b9d93b3f998e",
                    "name": "qc_suggested_max_tokens",
                    "value": "={{   (() => {     const raw = $json.body.choices[0].message.content || \"\";     const cleaned = raw       .replace(/```json\\s*([\\s\\S]*?)```/i, '$1')       .replace(/```\\s*([\\s\\S]*?)```/i, '$1')       .trim();     const qc = JSON.parse(cleaned);     return qc.suggested_max_tokens || null;   })() }}",
                    "type": "number"
                },
                {
                    "id": "0ce99028-1700-4f11-a2ef-bf563388b341",
                    "name": "qc_suggested_extra_context_append",
                    "value": "={{   (() => {     const raw = $json.body.choices[0].message.content || \"\";     const cleaned = raw       .replace(/```json\\s*([\\s\\S]*?)```/i, '$1')       .replace(/```\\s*([\\s\\S]*?)```/i, '$1')       .trim();     const qc = JSON.parse(cleaned);     return qc.suggested_extra_context_append || '';   })() }}",
                    "type": "string"
                },
                {
                    "id": "7a8c0b5e-def6-4616-9604-be7cabf666d9",
                    "name": "qc_recommended_actions",
                    "value": "={{   (() => {     const raw = $json.body.choices[0].message.content || \"\";     const cleaned = raw       .replace(/```json\\s*([\\s\\S]*?)```/i, '$1')       .replace(/```\\s*([\\s\\S]*?)```/i, '$1')       .trim();     const qc = JSON.parse(cleaned);     return JSON.stringify(qc.recommended_actions || []);   })() }}",
                    "type": "string"
                },
                {
                    "id": "5ecf57ce-9340-4a3a-94a1-050bae3f5e28",
                    "name": "qc_strengths_summary",
                    "value": "={{   (() => {     const raw = $json.body.choices[0].message.content || \"\";     const cleaned = raw       .replace(/```json\\s*([\\s\\S]*?)```/i, '$1')       .replace(/```\\s*([\\s\\S]*?)```/i, '$1')       .trim();     const qc = JSON.parse(cleaned);     return JSON.stringify(qc.strengths_summary || []);   })() }}",
                    "type": "string"
                },
                {
                    "id": "d0c5cae8-e895-4039-8eec-dbeb9e5e41e5",
                    "name": "qc_optional_improvements",
                    "value": "={{   (() => {     const raw = $json.body.choices[0].message.content || \"\";     const cleaned = raw       .replace(/```json\\s*([\\s\\S]*?)```/i, '$1')       .replace(/```\\s*([\\s\\S]*?)```/i, '$1')       .trim();     const qc = JSON.parse(cleaned);     return JSON.stringify(qc.optional_improvements || []);   })() }}",
                    "type": "string"
                }
            ]
        },
        "options": {}
    };

    @node({
        name: "Merge",
        type: "n8n-nodes-base.merge",
        version: 3.2,
        position: [2784, -272]
    })
    Merge = {
        "mode": "combine",
        "combineBy": "combineByPosition",
        "options": {}
    };

    @node({
        name: "1 - raw text in",
        type: "n8n-nodes-base.set",
        version: 3.4,
        position: [1440, -368]
    })
    _1RawTextIn = {
        "assignments": {
            "assignments": [
                {
                    "id": "ebdb493e-2055-4902-b7b5-431714697d97",
                    "name": "raw_text",
                    "value": "={{ $json.body.choices[0].message.content }}",
                    "type": "string"
                }
            ]
        },
        "includeOtherFields": true,
        "options": {}
    };

    @node({
        name: "2 - split think",
        type: "n8n-nodes-base.set",
        version: 3.4,
        position: [1664, -368]
    })
    _2SplitThink = {
        "assignments": {
            "assignments": [
                {
                    "id": "6fa353f1-4d09-42da-bb88-0fa4521a2293",
                    "name": "think_block",
                    "value": "={{ $json.raw_text.match(/<think>[\\s\\S]*?<\\/think>/i) }}\n",
                    "type": "string"
                },
                {
                    "id": "1e886a4a-f2b9-4bb0-893a-411f2639cf81",
                    "name": "step2_no_think",
                    "value": "={{ $json.raw_text.replace(/<think>[\\s\\S]*?<\\/think>/gi, \"\") }}\n",
                    "type": "string"
                }
            ]
        },
        "includeOtherFields": true,
        "options": {}
    };

    @node({
        name: "3 - strip fences",
        type: "n8n-nodes-base.set",
        version: 3.4,
        position: [1888, -368]
    })
    _3StripFences = {
        "assignments": {
            "assignments": [
                {
                    "id": "6516e7f6-1427-4951-b9b7-d3dc0c8c5d8f",
                    "name": "step3_no_fences",
                    "value": "={{ \n  (() => {\n    const s = $json.step2_no_think || '';\n    // Trim whitespace first\n    let t = s.trim();\n    // Remove a single outer `````` or `````` pair only\n    t = t.replace(/^``````$/i, '$1');\n    t = t.replace(/^``````$/i, '$1');\n    return t.trim();\n  })()\n}}\n\n",
                    "type": "string"
                }
            ]
        },
        "includeOtherFields": true,
        "options": {}
    };

    @node({
        name: "4 - slice JSON",
        type: "n8n-nodes-base.set",
        version: 3.4,
        position: [2112, -368]
    })
    _4SliceJson = {
        "assignments": {
            "assignments": [
                {
                    "id": "44f768aa-c168-4fbe-b4d6-bf3b5b689f13",
                    "name": "json_slice",
                    "value": "={{\n  (() => {\n    const s = $json.step3_no_fences || '';\n    const start = s.indexOf('{');\n    const end = s.lastIndexOf('}');\n    if (start === -1 || end === -1 || end <= start) {\n      return s.trim(); // fallback: no slicing\n    }\n    const candidate = s.substring(start, end + 1);\n    return candidate.trim();\n  })()\n}}\n",
                    "type": "string"
                }
            ]
        },
        "includeOtherFields": true,
        "options": {}
    };

    @node({
        name: "5 - parse JSON",
        type: "n8n-nodes-base.set",
        version: 3.4,
        position: [2336, -368]
    })
    _5ParseJson = {
        "assignments": {
            "assignments": [
                {
                    "id": "3661b94d-497c-4479-944c-e211eca5e7e5",
                    "name": "llm_output_clean",
                    "value": "={{ $json.json_slice }}\n\n",
                    "type": "string"
                }
            ]
        },
        "includeOtherFields": true,
        "options": {}
    };

    @node({
        name: "Insert row",
        type: "n8n-nodes-base.dataTable",
        version: 1,
        position: [3456, -176]
    })
    InsertRow = {
        "dataTableId": {
            "__rl": true,
            "value": "zyCfWBIbaG1z8YOL",
            "mode": "list",
            "cachedResultName": "tender_agent_llm_store",
            "cachedResultUrl": "/projects/FINYdRRpzfX9wIho/datatables/zyCfWBIbaG1z8YOL"
        },
        "columns": {
            "mappingMode": "defineBelow",
            "value": {
                "key": "={{ $('Prepare result for storage').item.json.store.run_id }}",
                "value": "={{ $('Prepare result for storage').item.json.llm_output_clean1 }}"
            },
            "matchingColumns": [],
            "schema": [
                {
                    "id": "key",
                    "displayName": "key",
                    "required": false,
                    "defaultMatch": false,
                    "display": true,
                    "type": "string",
                    "readOnly": false,
                    "removed": false
                },
                {
                    "id": "value",
                    "displayName": "value",
                    "required": false,
                    "defaultMatch": false,
                    "display": true,
                    "type": "string",
                    "readOnly": false,
                    "removed": false
                }
            ],
            "attemptToConvertTypes": false,
            "convertFieldsToString": false
        },
        "options": {}
    };

    @node({
        name: "Create 'Clean1' for storage",
        type: "n8n-nodes-base.set",
        version: 3.4,
        position: [3008, -272]
    })
    CreateClean1ForStorage = {
        "assignments": {
            "assignments": [
                {
                    "id": "b5b09dff-a780-43b0-a234-b2915645c03f",
                    "name": "llm_output_clean1",
                    "value": "={{\n  ($json.llm_output_raw || '')\n    // normalize CR/LF to space\n    .replace(/\\r\\n/g, ' ')\n    .replace(/[\\r\\n]/g, ' ')\n    // strip other ASCII control chars\n    .replace(/[\\u0000-\\u001F\\u007F]/g, ' ')\n}}",
                    "type": "string"
                }
            ]
        },
        "includeOtherFields": true,
        "options": {}
    };


    // =====================================================================
// ROUTAGE ET CONNEXIONS
// =====================================================================

    @links()
    defineRouting() {
        this.Webhook.out(0).to(this.SecretCheck.in(0));
        this.CheckInput.out(0).to(this.NormaliseInputs.in(0));
        this.CheckInput.out(1).to(this.RespondToWebhook2.in(0));
        this.NormaliseInputs.out(0).to(this.PerplexityHttpRequest1.in(0));
        this.SanitizePerplexityOutput.out(0).to(this.Merge.in(0));
        this.PerplexityHttpRequest1.out(0).to(this.QcPromptPrep.in(0));
        this.PerplexityHttpRequest1.out(0).to(this._1RawTextIn.in(0));
        this.PrepareResultForStorage.out(0).to(this.RespondToWebhook.in(0));
        this.PrepareResultForStorage.out(0).to(this.InsertRow.in(0));
        this.PrepareResultForStorage.out(0).to(this.AppendRowInEchoStatusSheet.in(0));
        this.SecretCheck.out(0).to(this.CheckInput.in(0));
        this.SecretCheck.out(1).to(this.RespondToWebhook1.in(0));
        this.QcPromptPrep.out(0).to(this.PerplexityQcCritic.in(0));
        this.PerplexityQcCritic.out(0).to(this.TidyQcOutputs.in(0));
        this.TidyQcOutputs.out(0).to(this.Merge.in(1));
        this.Merge.out(0).to(this.CreateClean1ForStorage.in(0));
        this._1RawTextIn.out(0).to(this._2SplitThink.in(0));
        this._2SplitThink.out(0).to(this._3StripFences.in(0));
        this._3StripFences.out(0).to(this._4SliceJson.in(0));
        this._4SliceJson.out(0).to(this._5ParseJson.in(0));
        this._5ParseJson.out(0).to(this.SanitizePerplexityOutput.in(0));
        this.CreateClean1ForStorage.out(0).to(this.PrepareResultForStorage.in(0));
    }
}