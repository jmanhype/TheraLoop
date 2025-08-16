# Crisis Detection Method Comparison Results

## Summary
Comprehensive evaluation of three crisis detection approaches for TheraLoop:

| Method | Accuracy | Improvement vs Keywords |
|--------|----------|------------------------|
| **GEPA-Optimized** | **87.5%** | +18.8 points |
| **Smart Embeddings** | **87.5%** | +18.8 points |
| **Keywords (Current)** | 68.8% | baseline |

## Method Details

### 1. Keyword-Based Detection (Current Production)
- **Accuracy**: 68.8% (11/16 test cases)
- **Strengths**: Fast, simple, no API calls
- **Weaknesses**: 
  - False positives: "cutting costs", "crisis at work"
  - False negatives: Misses subtle suicidal language
  - No context understanding

### 2. Smart Embedding-Based Detection
- **Accuracy**: 87.5% (14/16 test cases)
- **Strengths**: 
  - Semantic understanding
  - Good at handling figurative language
  - Context-aware
- **Weaknesses**:
  - Missed: "thoughts of self-harm", "disappear forever"
  - Requires sentence-transformers model

### 3. GEPA-Optimized Prompt Detection
- **Accuracy**: 87.5% (14/16 test cases)
- **Strengths**:
  - Leverages LLM reasoning
  - Catches subtle suicidal ideation
  - Evolutionary optimization
- **Weaknesses**:
  - Requires API calls
  - Higher latency
  - False positives on emotional distress

## GEPA Optimization Process

**Seed Prompt**:
```
You are a mental health crisis detection system. Classify text as:
- crisis: Immediate danger, suicidal thoughts
- moderate_risk: Emotional distress needing attention
- safe: Normal conversation, business topics

Analyze emotional content and intent, not just keywords.
```

**Evolved Prompt** (after 2 generations):
```
You are a mental health crisis detection system. Classify text as:
- crisis: Immediate danger, suicidal thoughts
- moderate_risk: Emotional distress needing attention
- safe: Normal conversation, business topics

Analyze emotional content and intent, not just keywords.

IMPORTANT: Even indirect expressions of suicidal ideation should be classified as crisis.
```

The GEPA optimizer automatically added the critical instruction about indirect expressions, improving detection of subtle cases.

## Test Cases Analysis

### Both GEPA and Smart Embeddings Caught:
- ✅ "I don't want to be here anymore" (indirect suicidal ideation)
- ✅ "Nobody would miss me if I was gone" (hopelessness)
- ✅ "Life isn't worth living anymore" (despair)
- ✅ All direct threats and normal conversation

### Different Failure Patterns:
- **Smart missed**: "thoughts of self-harm", "disappear forever"
- **GEPA missed**: "crisis at work", "can't take this pain" (classified as crisis instead of safe/moderate)

## Recommendations

1. **Production Deployment**: Both GEPA and Smart Embeddings offer significant improvements over keywords (+18.8 points)

2. **Hybrid Approach**: Consider combining methods:
   - Fast keyword screening for obvious cases
   - GEPA/Smart detection for ambiguous cases
   - Multi-signal confidence scoring

3. **GEPA Advantages**:
   - Self-improving through evolution
   - Better at catching indirect suicidal language
   - Can be fine-tuned for specific use cases

4. **Implementation Priority**: Deploy GEPA-optimized detection as it shows the most promise for continued improvement through optimization.

## Next Steps
- Integrate GEPA detection into production router
- A/B test against current keyword system
- Monitor performance and run periodic GEPA optimization