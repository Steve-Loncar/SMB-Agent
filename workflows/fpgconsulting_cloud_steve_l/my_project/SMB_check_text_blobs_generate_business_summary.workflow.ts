import { workflow, node, links } from '@n8n-as-code/transformer';

// <workflow-map>
// Workflow : SMB_check_text_blobs_generate_business_summary
// Nodes   : 8  |  Connections: 7
//
// NODE INDEX
// ──────────────────────────────────────────────────────────────────
// Property name                    Node type (short)         Flags
// Webhook                            webhook                    
// HttpRequest                        httpRequest                [creds]
// RespondToWebhook                   respondToWebhook           
// EditFields                         set                        
// _1RawTextIn                        set                        
// _3StripFences                      set                        
// PrepareResponsePayload             set                        
// PrepareResponse                    set                        
//
// ROUTING MAP
// ──────────────────────────────────────────────────────────────────
// Webhook
//    → EditFields
//      → HttpRequest
//        → _1RawTextIn
//          → _3StripFences
//            → PrepareResponsePayload
//              → PrepareResponse
//                → RespondToWebhook
// </workflow-map>

// =====================================================================
// METADATA DU WORKFLOW
// =====================================================================

@workflow({
    id: "MPLFXEKhILpVNwJE",
    name: "SMB_check_text_blobs_generate_business_summary",
    active: true,
    settings: {executionOrder:"v1",availableInMCP:false}
})
export class SmbCheckTextBlobsGenerateBusinessSummaryWorkflow {

    // =====================================================================
// CONFIGURATION DES NOEUDS
// =====================================================================

    @node({
        name: "Webhook",
        type: "n8n-nodes-base.webhook",
        version: 2.1,
        position: [1552, 64]
    })
    Webhook = {
        "httpMethod": "POST",
        "path": "check-text-blobs",
        "responseMode": "responseNode",
        "options": {}
    };

    @node({
        name: "HTTP Request",
        type: "n8n-nodes-base.httpRequest",
        version: 4.3,
        position: [2000, 64],
        credentials: {perplexityApi:{id:"SkSOGLP98gXnuOBu",name:"Perplexity account"}}
    })
    HttpRequest = {
        "method": "POST",
        "url": "https://api.perplexity.ai/chat/completions",
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "perplexityApi",
        "sendBody": true,
        "bodyParameters": {
            "parameters": [
                {
                    "name": "model",
                    "value": "sonar-pro"
                },
                {
                    "name": "temperature",
                    "value": "0.4"
                },
                {
                    "name": "messages",
                    "value": "={{ [\n  {\n    \"role\": \"system\",\n    \"content\": \"You are a media strategy + creative assistant. Return ONLY valid JSON. No markdown, no commentary.\"\n  },\n  {\n    \"role\": \"user\",\n    \"content\": \"Business website: \" + $json.url + \"\\n\\nWebsite text:\\n\" + $json.scraped_text + \"\\n\\nReturn JSON with exactly this schema:\\n{\\n  \\\"business_summary\\\": {\\n    \\\"name_guess\\\": \\\"string\\\",\\n    \\\"category\\\": \\\"string\\\",\\n    \\\"target_customer\\\": \\\"string\\\",\\n    \\\"value_prop\\\": \\\"string\\\",\\n    \\\"tone\\\": \\\"string\\\",\\n    \\\"key_offers\\\": [\\\"string\\\"],\\n    \\\"key_proof_points\\\": [\\\"string\\\"],\\n    \\\"key_ctas\\\": [\\\"string\\\"]\\n  },\\n  \\\"poster_concepts\\\": [\\n    {\\n      \\\"concept_name\\\": \\\"string\\\",\\n      \\\"headline\\\": \\\"string\\\",\\n      \\\"supporting_copy\\\": \\\"string\\\",\\n      \\\"cta\\\": \\\"string\\\",\\n      \\\"layout_notes\\\": \\\"string\\\",\\n      \\\"image_idea\\\": \\\"string\\\",\\n      \\\"style_tags\\\": [\\\"string\\\"]\\n    }\\n  ]\\n}\\n\\nRules:\\n- UK local OOH posters\\n- Headlines <= 7 words\\n- supporting_copy <= 25 words\\n- Provide 3 poster_concepts\\n- If unknown, make best guess from website text\"\n  }\n] }}"
                }
            ]
        },
        "options": {}
    };

    @node({
        name: "Respond to Webhook",
        type: "n8n-nodes-base.respondToWebhook",
        version: 1.5,
        position: [3056, 64]
    })
    RespondToWebhook = {
        "respondWith": "allIncomingItems",
        "options": {}
    };

    @node({
        name: "Edit Fields",
        type: "n8n-nodes-base.set",
        version: 3.4,
        position: [1776, 64]
    })
    EditFields = {
        "assignments": {
            "assignments": [
                {
                    "id": "81ffadd2-885c-42e0-8681-21780b4605c8",
                    "name": "url",
                    "value": "={{ $json.body.url }}",
                    "type": "string"
                },
                {
                    "id": "4d316c00-f616-469a-810f-33880da4a6a4",
                    "name": "scrape_pack",
                    "value": "={{ $json.body.scrape_pack }}",
                    "type": "string"
                },
                {
                    "id": "c7fcfaf7-9c97-424d-864b-76d8cbc6a9c3",
                    "name": "payload_type",
                    "value": "={{ $json.body.payload_type }}",
                    "type": "string"
                },
                {
                    "id": "1c33bf2e-384c-4ecd-918f-f63443c3702c",
                    "name": "has_scapre_pack",
                    "value": "={{ Array.isArray($json.body.scrape_pack) || !!$json.body.scrape_pack?.scrape_pack }}",
                    "type": "string"
                }
            ]
        },
        "options": {}
    };

    @node({
        name: "1 - Raw text in",
        type: "n8n-nodes-base.set",
        version: 3.4,
        position: [2208, 64]
    })
    _1RawTextIn = {
        "assignments": {
            "assignments": [
                {
                    "id": "02f5f0e7-ce7d-4d54-9da3-642ae10ba677",
                    "name": "raw_text",
                    "value": "={{ $json.choices[0].message.content }}",
                    "type": "string"
                }
            ]
        },
        "options": {}
    };

    @node({
        name: "3 - strip fences",
        type: "n8n-nodes-base.set",
        version: 3.4,
        position: [2416, 64]
    })
    _3StripFences = {
        "assignments": {
            "assignments": [
                {
                    "id": "9b33aebe-9c95-407e-a40f-bf35430000aa",
                    "name": "no_fences",
                    "value": "={{ \n  (() => {\n    const raw = $json.raw_text || \"\";\n    const cleaned = raw\n      .replace(/```json\\s*([\\s\\S]*?)```/i, '$1')\n      .replace(/```\\s*([\\s\\S]*?)```/i, '$1')\n      .trim();\n    return cleaned;\n  })()\n}}",
                    "type": "string"
                }
            ]
        },
        "options": {}
    };

    @node({
        name: "prepare response payload",
        type: "n8n-nodes-base.set",
        version: 3.4,
        position: [2624, 64]
    })
    PrepareResponsePayload = {
        "assignments": {
            "assignments": [
                {
                    "id": "564b627e-476c-4a4e-9eb4-a2ae4f477a85",
                    "name": "parsed",
                    "value": "={{ JSON.parse($json.no_fences) }}",
                    "type": "object"
                }
            ]
        },
        "options": {}
    };

    @node({
        name: "Prepare response",
        type: "n8n-nodes-base.set",
        version: 3.4,
        position: [2832, 64]
    })
    PrepareResponse = {
        "assignments": {
            "assignments": [
                {
                    "id": "991b63fb-0b0f-477f-916d-7428031bd8b8",
                    "name": "business_summary",
                    "value": "={{ $json.parsed.business_summary }}",
                    "type": "object"
                },
                {
                    "id": "fde40cb4-0e28-4395-9d15-2d96df30e9a5",
                    "name": "poster_concepts",
                    "value": "={{ $json.parsed.poster_concepts }}",
                    "type": "array"
                },
                {
                    "id": "419eff4e-d638-4752-8d52-a875c68e7900",
                    "name": "",
                    "value": "",
                    "type": "string"
                }
            ]
        },
        "options": {}
    };


    // =====================================================================
// ROUTAGE ET CONNEXIONS
// =====================================================================

    @links()
    defineRouting() {
        this.Webhook.out(0).to(this.EditFields.in(0));
        this.HttpRequest.out(0).to(this._1RawTextIn.in(0));
        this.EditFields.out(0).to(this.HttpRequest.in(0));
        this._1RawTextIn.out(0).to(this._3StripFences.in(0));
        this._3StripFences.out(0).to(this.PrepareResponsePayload.in(0));
        this.PrepareResponsePayload.out(0).to(this.PrepareResponse.in(0));
        this.PrepareResponse.out(0).to(this.RespondToWebhook.in(0));
    }
}