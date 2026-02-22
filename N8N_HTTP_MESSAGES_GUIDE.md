# 📚 N8N HTTP Request Messages Field Guide

> **The definitive reference for constructing OpenAI/Perplexity API `messages` parameters in n8n workflows**

## 🎯 THE GOLDEN RULES

1. **The `messages` parameter MUST be an array of message objects**
2. **The `content` field MUST be a STRING** (never an object or array)
3. **When passing object/array data, use `JSON.stringify()` and concatenate it into the content string**
4. **Test with simple strings first, then add complexity**

---

## ✅ Working Patterns (Copy & Use These)

### Pattern 1: Simple String References

**Use when:** Your data is already prepared as strings in previous Set nodes.

```javascript
"messages": "={{[
  {
    role: 'system',
    content: ($json.prompt_system)
  },
  {
    role: 'user',
    content: ($json.prompt_user)
  }
]}}"
```

**✓ Pros:**
- Clean and readable
- Fast execution
- Easy to debug

**✗ Cons:**
- Requires preparation in Set node
- Less flexible for dynamic content

**Real-world example:**
```javascript
// In a Set node before the HTTP request:
{
  "prompt_system": "You are a helpful assistant",
  "prompt_user": "Analyze this data..."
}

// Then in HTTP Request node:
"messages": "={{[
  { role: 'system', content: ($json.prompt_system) },
  { role: 'user', content: ($json.prompt_user) }
]}}"
```

---

### Pattern 2: String Concatenation with JSON.stringify() ⭐ RECOMMENDED

**Use when:** You need to include complex objects/arrays in your prompt.

```javascript
"messages": "={{[
  {
    role: 'system',
    content: ($json.prompt_system)
  },
  {
    role: 'user',
    content: ($json.prompt_user) +
      '\n\nBUSINESS SUMMARY:\n' +
      JSON.stringify(($json.business_summary) || {}) +
      '\n\nPAGE SUMMARIES:\n' +
      JSON.stringify(($json.page_summaries) || []) +
      '\n\nADDITIONAL CONTEXT:\n' +
      ($json.extra_context || '')
  }
]}}"
```

**✓ Pros:**
- Most flexible pattern
- No intermediate Set nodes needed
- Clear data structure in prompt
- LLM can parse the JSON

**✗ Cons:**
- Can get long/verbose
- Requires careful escaping

**Tips:**
- Add clear section headers (e.g., `\n\nSECTION NAME:\n`)
- Use `|| {}` or `|| []` for fallbacks
- Format JSON for readability if needed: `JSON.stringify($json.data, null, 2)`

---

### Pattern 3: Multi-field String Building

**Use when:** Combining many individual fields into a structured prompt.

```javascript
"messages": "={{[
  {
    role: 'system',
    content: ($json.system_prompt)
  },
  {
    role: 'user',
    content:
      'User question: ' + ($json.question) +
      '\n\nContext: ' + ($json.context) +
      '\n\nMetadata:' +
      '\n  - ID: ' + ($json.tender_id) +
      '\n  - Type: ' + ($json.question_type) +
      '\n\nEvidence:\n' + ($json.evidence_text)
  }
]}}"
```

**✓ Pros:**
- Very readable
- Easy to maintain
- Good for structured data

**✗ Cons:**
- Can become verbose
- Manual formatting required

---

### Pattern 4: Template Substitution (Pre-process in Set Node)

**Use when:** You have complex prompt templates with multiple placeholders.

**Step 1 - Set node (prepare templated prompt):**
```javascript
{
  "assignments": [
    {
      "name": "user_prompt",
      "value": "={{ 
        $json.prompt_template
          .split('{concept}').join(JSON.stringify($json.concept))
          .split('{guidelines}').join(JSON.stringify($json.guidelines))
          .split('{urls}').join(JSON.stringify($json.image_urls))
      }}",
      "type": "string"
    }
  ]
}
```

**Step 2 - HTTP Request node:**
```javascript
"messages": "={{[
  { role: 'system', content: ($json.system_prompt) },
  { role: 'user', content: ($json.user_prompt) }
]}}"
```

**✓ Pros:**
- Separates templating logic from API call
- Reusable prompt templates
- Easy to debug intermediate output

**✗ Cons:**
- Extra Set node required
- More steps in workflow

---

## ❌ Anti-Patterns (Don't Do This!)

### ❌ Passing Objects Directly

```javascript
// WRONG - Will fail!
"messages": "={{[
  {
    role: 'user',
    content: {
      concept: $json.poster_concept,     // ❌ Object!
      guidelines: $json.guidelines       // ❌ Object!
    }
  }
]}}"
```

**Error:** OpenAI API expects `content` to be a string, will throw validation error.

**Fix:** Use `JSON.stringify()` and concatenate:
```javascript
// RIGHT ✓
"messages": "={{[
  {
    role: 'user',
    content: 
      'CONCEPT:\n' + JSON.stringify($json.poster_concept) +
      '\n\nGUIDELINES:\n' + JSON.stringify($json.guidelines)
  }
]}}"
```

---

### ❌ Forgetting to Stringify Arrays

```javascript
// WRONG
"content": ($json.image_urls)  // array reference

// RIGHT ✓
"content": JSON.stringify($json.image_urls)
// or
"content": 'Images: ' + ($json.image_urls.join(', '))
```

---

### ❌ Unescaped Quotes in Strings

```javascript
// WRONG - breaks JSON
"content": "The user said "hello""

// RIGHT ✓
"content": "The user said \"hello\""
// or
"content": 'The user said "hello"'
```

---

## 🔧 Debugging Tips

### 1. **Add a Set node after your HTTP request to inspect the output**

```javascript
{
  "assignments": [
    {
      "name": "debug_messages",
      "value": "={{ JSON.stringify($('HTTP Request').item.json.choices[0].message) }}",
      "type": "string"
    }
  ]
}
```

### 2. **Use console.log equivalent in expressions**

```javascript
"messages": "={{
  // Log the data structure
  console.log('Data:', $json.business_summary);
  
  return [{
    role: 'system',
    content: ($json.system_prompt)
  }];
}}"
```

### 3. **Test with minimal data first**

Start with:
```javascript
"messages": "={{[
  { role: 'user', content: 'test' }
]}}"
```

Then gradually add complexity.

### 4. **Check for undefined/null values**

```javascript
"content": 
  'Summary: ' + (($json.summary) || 'No summary available') +
  '\n\nData: ' + JSON.stringify(($json.data) || {})
```

---

## 📋 Quick Reference Table

| Scenario | Pattern | Example |
|----------|---------|---------|
| Simple string fields | Direct reference | `content: ($json.prompt)` |
| Object/array data | JSON.stringify + concat | `'Data:\n' + JSON.stringify($json.obj)` |
| Multiple objects | Multi-line concat | See Pattern 2 above |
| Complex templates | Set node + substitution | See Pattern 4 above |
| Conditional content | Ternary operators | `($json.summary ? JSON.stringify($json.summary) : 'N/A')` |
| Joining arrays | Array methods | `($json.urls.join('\n'))` |

---

## 🎓 Best Practices

### 1. **Structure Your Prompts with Clear Headers**

```javascript
"content": 
  '===== INSTRUCTIONS =====\n' +
  ($json.instructions) +
  '\n\n===== DATA =====\n' +
  JSON.stringify($json.data) +
  '\n\n===== OUTPUT FORMAT =====\n' +
  ($json.output_format)
```

### 2. **Use Fallbacks for Optional Data**

```javascript
"content":
  'Required: ' + ($json.required_field) +
  '\nOptional: ' + (($json.optional_field) || 'Not provided')
```

### 3. **Format JSON for Readability (when appropriate)**

```javascript
// Compact (default)
JSON.stringify($json.data)

// Pretty-printed
JSON.stringify($json.data, null, 2)
```

### 4. **Handle Errors Gracefully**

```javascript
"content":
  'Summary: ' + 
  (typeof $json.summary === 'object' 
    ? JSON.stringify($json.summary) 
    : String($json.summary || 'N/A'))
```

### 5. **Keep System Prompts Separate and Reusable**

Store system prompts in:
- Workflow static data
- Set nodes at the start
- External files loaded via HTTP/Code nodes

---

## 🚀 Performance Tips

1. **Minimize Set nodes:** Use direct concatenation in HTTP node when possible
2. **Batch stringify calls:** `JSON.stringify({obj1: $json.obj1, obj2: $json.obj2})`
3. **Use template literals wisely:** Don't over-nest expressions
4. **Cache repeated values:** Store in Set node if used multiple times

---

## 📚 Real-World Examples

### Example 1: SMB Ad Generation

```javascript
"messages": "={{[
  {
    role: 'system',
    content: ($json.prompt_system)
  },
  {
    role: 'user',
    content: ($json.prompt_user) +
      '\n\nBUSINESS SUMMARY:\n' +
      JSON.stringify(($json.body.business_summary) || {}) +
      '\n\nTIER 1 & 2 PAGE SUMMARIES:\n' +
      JSON.stringify(($json.page_summaries) || [])
  }
]}}"
```

### Example 2: Tender Analysis

```javascript
"messages": "={{[
  {
    role: 'system',
    content: ($json.prompt_text)
  },
  {
    role: 'user',
    content:
      'Global tender context:\n' + ($json.global_context) +
      '\n\nTender question:\n' + ($json.tender_question) +
      '\n\nAuthority: ' + ($json.authority_name) +
      '\n\nMetadata: tender_id=' + ($json.tender_id) +
      '; question_id=' + ($json.question_id) +
      '\n\nEvidence:\n' + ($json.evidence_input)
  }
]}}"
```

### Example 3: Multi-Step Processing (Image Selection → Poster Generation)

**Step A - Image Selection:**
```javascript
"messages": "={{[
  { role: 'system', content: ($json.selection_system) },
  { role: 'user', content: 
      'CONCEPT:\n' + JSON.stringify($json.concept) +
      '\n\nGUIDELINES:\n' + JSON.stringify($json.guidelines) +
      '\n\nAVAILABLE IMAGES:\n' + JSON.stringify($json.image_urls)
  }
]}}"
```

**Step B - Extract & Use Results:**
```javascript
// Set node to parse response
{
  "selected_images": "={{ JSON.parse($json.choices[0].message.content).selected_images }}"
}

// Then use in next HTTP request
"messages": "={{[
  { role: 'system', content: ($json.poster_system) },
  { role: 'user', content:
      'CONCEPT:\n' + JSON.stringify($json.concept) +
      '\n\nSELECTED IMAGES:\n' + JSON.stringify($json.selected_images)
  }
]}}"
```

---

## 🆘 Troubleshooting Guide

| Error | Likely Cause | Fix |
|-------|--------------|-----|
| "Invalid type for messages" | Passing object in `content` | Wrap with `JSON.stringify()` |
| "Unexpected token" | Syntax error in expression | Check quotes, brackets, parentheses |
| Empty/null content | Field doesn't exist | Add fallback: `($json.field \|\| 'default')` |
| Escaped characters broken | String escaping issue | Use single quotes or escape properly |
| Content too long | Exceeding token limits | Truncate or summarize data before stringify |

---

## 📖 Additional Resources

- [n8n Expression Documentation](https://docs.n8n.io/code/expressions/)
- [OpenAI API Messages Format](https://platform.openai.com/docs/api-reference/chat/create)
- [JavaScript Template Literals](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Template_literals)

---

## ✨ Template Starter Kit

Copy this into any new HTTP Request node:

```javascript
{
  "method": "POST",
  "url": "https://api.openai.com/v1/chat/completions",
  "authentication": "predefinedCredentialType",
  "nodeCredentialType": "openAiApi",
  "sendBody": true,
  "bodyParameters": {
    "parameters": [
      {
        "name": "model",
        "value": "gpt-4o"
      },
      {
        "name": "messages",
        "value": "={{[\n  {\n    role: 'system',\n    content: ($json.prompt_system)\n  },\n  {\n    role: 'user',\n    content: ($json.prompt_user) +\n      '\\n\\nDATA:\\n' +\n      JSON.stringify(($json.data) || {})\n  }\n]}}"
      }
    ]
  },
  "options": {
    "response": {
      "response": {
        "responseFormat": "json"
      }
    },
    "timeout": 60000
  }
}
```

---

**Last Updated:** February 2026  
**Version:** 1.0  
**Validated Against:** n8n v1.x, OpenAI API v1, Perplexity API
