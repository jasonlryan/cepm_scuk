"""
Rule-based scoring engine for CEPM.

Scores creative assets against donor personas based on
analysis data provided by ChatGPT or Claude.
"""


def score_creative(analysis_data, persona, asset_type, user_context=None):
    """
    Score a creative asset against a persona.

    Args:
        analysis_data: Structured analysis from ChatGPT/Claude
        persona: Persona definition dict
        asset_type: "copy", "image", or "campaign"
        user_context: Optional dict with campaign_goal, channel, etc.

    Returns:
        Dict with overall score and sub-scores (all 0.0 to 1.0)
    """
    if asset_type == 'copy':
        scores = _score_copy(analysis_data, persona)
    elif asset_type == 'image':
        scores = _score_image(analysis_data, persona)
    elif asset_type == 'campaign':
        scores = _score_campaign(analysis_data, persona)
    else:
        scores = _score_copy(analysis_data, persona)

    # Apply channel bonus if context provided
    if user_context and 'channel' in user_context:
        channel = user_context['channel']
        preferred = persona.get('preferred_channels', [])
        if channel in preferred:
            scores['channel_fit'] = 1.0
        else:
            scores['channel_fit'] = 0.4

    # Calculate overall score (weighted average)
    scores['overall'] = _calculate_overall(scores, asset_type)

    # Clamp all scores to 0-1
    return {k: round(max(0.0, min(1.0, v)), 2) for k, v in scores.items()}


def _score_copy(analysis, persona):
    """Score text/copy-based creative assets."""
    scores = {}

    # Emotional impact: how well content's emotional tone matches persona triggers
    scores['emotional_impact'] = _score_emotional_match(
        analysis.get('emotional_tone', {}),
        analysis.get('sentiment', {}),
        persona.get('emotional_triggers', [])
    )

    # Clarity: readability appropriate for the persona
    scores['clarity'] = _score_clarity(
        analysis.get('readability', {}),
        analysis.get('tone', {}),
        persona.get('communication_preferences', {})
    )

    # Persona alignment: overall tone/theme match
    scores['persona_alignment'] = _score_copy_alignment(
        analysis.get('tone', {}),
        analysis.get('key_themes', []),
        persona
    )

    # CTA effectiveness: how well the call-to-action works for this persona
    scores['cta_effectiveness'] = _score_cta(
        analysis.get('cta_assessment', {}),
        persona.get('response_patterns', {})
    )

    return scores


def _score_image(analysis, persona):
    """Score image-based creative assets."""
    scores = {}

    # Emotional impact from image
    scores['emotional_impact'] = _score_emotional_match(
        analysis.get('emotional_tone', {}),
        {},
        persona.get('emotional_triggers', [])
    )

    # Visual appeal: how well visuals match persona preferences
    scores['visual_appeal'] = _score_visual_match(
        analysis.get('visual_elements', {}),
        persona.get('visual_preferences', {})
    )

    # Persona alignment for images
    scores['persona_alignment'] = _score_image_alignment(
        analysis.get('visual_elements', {}),
        analysis.get('audience_appeal', {}),
        persona
    )

    # Brand consistency (pass-through from analysis if provided)
    scores['brand_consistency'] = analysis.get('brand_consistency', 0.5)

    return scores


def _score_campaign(analysis, persona):
    """Score a full campaign (combines copy + image scoring)."""
    scores = {}

    copy_data = analysis.get('copy_analysis', {})
    image_data = analysis.get('image_analysis', {})

    if copy_data:
        copy_scores = _score_copy(copy_data, persona)
        for k, v in copy_scores.items():
            scores[f'copy_{k}'] = v

    if image_data:
        image_scores = _score_image(image_data, persona)
        for k, v in image_scores.items():
            scores[f'image_{k}'] = v

    # Campaign coherence: do copy and image work together?
    if copy_data and image_data:
        scores['coherence'] = _score_coherence(copy_data, image_data)

    # Overall emotional and alignment scores
    scores['emotional_impact'] = _avg([
        scores.get('copy_emotional_impact', 0.5),
        scores.get('image_emotional_impact', 0.5)
    ])
    scores['persona_alignment'] = _avg([
        scores.get('copy_persona_alignment', 0.5),
        scores.get('image_persona_alignment', 0.5)
    ])

    return scores


# --- Scoring helper functions ---

def _score_emotional_match(emotional_tone, sentiment, triggers):
    """Score how well emotional content matches persona triggers."""
    if not emotional_tone and not sentiment:
        return 0.5

    score = 0.0
    matches = 0
    total_checks = 0

    # Check primary/secondary emotional tone against triggers
    primary = emotional_tone.get('primary', '').lower()
    secondary = emotional_tone.get('secondary', '').lower()
    intensity = emotional_tone.get('intensity', 0.5)
    trigger_set = {t.lower() for t in triggers}

    # Emotional tone synonyms for fuzzy matching
    emotion_groups = {
        'compassion': {'compassion', 'empathy', 'caring', 'sympathy', 'kindness'},
        'hope': {'hope', 'optimism', 'inspiration', 'aspirational', 'uplifting'},
        'urgency': {'urgency', 'urgent', 'immediate', 'critical', 'time_sensitive'},
        'justice': {'justice', 'fairness', 'equality', 'rights', 'outrage'},
        'belonging': {'belonging', 'togetherness', 'community', 'solidarity', 'unity'},
        'pride': {'pride', 'achievement', 'accomplishment', 'success', 'progress'},
        'tradition': {'tradition', 'heritage', 'legacy', 'enduring', 'timeless'},
        'connection': {'connection', 'personal_stories', 'relationship', 'bond'},
        'gratitude': {'gratitude', 'thankfulness', 'appreciation', 'recognition'},
        'authenticity': {'authenticity', 'genuine', 'real', 'honest', 'raw'},
    }

    def fuzzy_match(emotion, triggers):
        if emotion in triggers:
            return True
        for group_emotions in emotion_groups.values():
            if emotion in group_emotions and group_emotions & triggers:
                return True
        return False

    if primary:
        total_checks += 1
        if fuzzy_match(primary, trigger_set):
            matches += 1

    if secondary:
        total_checks += 1
        if fuzzy_match(secondary, trigger_set):
            matches += 0.7  # secondary match is worth less

    if total_checks > 0:
        score = (matches / total_checks) * intensity
    else:
        score = 0.3

    # Sentiment boost: positive sentiment generally helps
    positive = sentiment.get('positive', 0.5)
    if positive > 0.6:
        score = min(1.0, score + 0.1)

    return max(0.0, min(1.0, score))


def _score_clarity(readability, tone, comm_prefs):
    """Score clarity based on readability and persona communication preferences."""
    score = 0.5

    # Readability score (0-100 scale, convert to 0-1)
    readability_score = readability.get('score', 50) / 100.0

    # Complexity assessment
    complexity = readability.get('complexity', 'moderate')
    pref_length = comm_prefs.get('message_length', 'medium')
    pref_formality = comm_prefs.get('formality', 0.5)

    # Match complexity to persona preference
    complexity_scores = {'simple': 0.2, 'moderate': 0.5, 'complex': 0.8}
    content_complexity = complexity_scores.get(complexity, 0.5)

    # Personas with low formality prefer simpler text
    complexity_diff = abs(content_complexity - pref_formality)
    complexity_match = 1.0 - complexity_diff

    # Tone formality match
    tone_formality = tone.get('formality', 0.5)
    formality_diff = abs(tone_formality - pref_formality)
    formality_match = 1.0 - formality_diff

    # Base readability is always good (higher = more readable)
    score = (readability_score * 0.3) + (complexity_match * 0.35) + (formality_match * 0.35)

    return max(0.0, min(1.0, score))


def _score_copy_alignment(tone, themes, persona):
    """Score overall copy alignment with persona."""
    score = 0.0
    components = 0

    comm_prefs = persona.get('communication_preferences', {})
    triggers = {t.lower() for t in persona.get('emotional_triggers', [])}
    motivations = {m.lower() for m in persona.get('donation_motivations', [])}

    # Tone match
    preferred_tone = comm_prefs.get('tone', '').lower()
    primary_tone = tone.get('primary', '').lower()
    secondary_tone = tone.get('secondary', '').lower()

    tone_synonyms = {
        'warm': {'warm', 'heartfelt', 'caring', 'gentle', 'compassionate'},
        'professional': {'professional', 'formal', 'business', 'corporate', 'polished'},
        'inclusive': {'inclusive', 'welcoming', 'collective', 'community', 'together'},
        'respectful': {'respectful', 'dignified', 'formal', 'thoughtful', 'considered'},
        'bold': {'bold', 'direct', 'provocative', 'edgy', 'challenging', 'punchy'},
        'inspirational': {'inspirational', 'uplifting', 'motivating', 'empowering'},
    }

    def tone_matches(content_tone, preferred):
        if content_tone == preferred:
            return True
        for synonyms in tone_synonyms.values():
            if content_tone in synonyms and preferred in synonyms:
                return True
        return False

    if preferred_tone and primary_tone:
        components += 1
        if tone_matches(primary_tone, preferred_tone):
            score += 1.0
        elif secondary_tone and tone_matches(secondary_tone, preferred_tone):
            score += 0.6

    # Theme/keyword alignment with triggers and motivations
    if themes:
        theme_set = {t.lower() for t in themes}
        target_set = triggers | motivations
        components += 1
        if target_set:
            overlap = len(theme_set & target_set)
            score += min(1.0, overlap / max(1, min(len(theme_set), len(target_set))))

    # Preferred language match
    pref_language = {w.lower() for w in comm_prefs.get('preferred_language', [])}
    if pref_language and themes:
        theme_set = {t.lower() for t in themes}
        components += 1
        overlap = len(theme_set & pref_language)
        score += min(1.0, overlap / max(1, len(pref_language)) + 0.2)

    if components > 0:
        return max(0.0, min(1.0, score / components))
    return 0.5


def _score_cta(cta_assessment, response_patterns):
    """Score call-to-action effectiveness for the persona."""
    if not cta_assessment:
        return 0.5

    clarity = cta_assessment.get('clarity', 0.5)
    urgency = cta_assessment.get('urgency', 0.5)
    persuasiveness = cta_assessment.get('persuasiveness', 0.5)

    urgency_sensitivity = response_patterns.get('urgency_sensitivity', 0.5)
    data_driven = response_patterns.get('data_driven', 0.5)
    story_driven = response_patterns.get('story_driven', 0.5)

    # Clarity is universally important
    score = clarity * 0.3

    # Urgency matters more for urgency-sensitive personas
    urgency_match = 1.0 - abs(urgency - urgency_sensitivity)
    score += urgency_match * 0.3

    # Persuasiveness weighted by what the persona responds to
    persuasion_weight = max(data_driven, story_driven)
    score += persuasiveness * persuasion_weight * 0.4

    return max(0.0, min(1.0, score))


def _score_visual_match(visual_elements, visual_prefs):
    """Score how well image visuals match persona visual preferences."""
    if not visual_elements or not visual_prefs:
        return 0.5

    score = 0.0
    components = 0

    # Color match
    content_colors = {c.lower() for c in visual_elements.get('dominant_colors', [])}
    pref_colors = {c.lower() for c in visual_prefs.get('colors', [])}
    if content_colors and pref_colors:
        components += 1
        overlap = len(content_colors & pref_colors)
        score += min(1.0, overlap / max(1, min(len(content_colors), len(pref_colors))))

    # Imagery/subject match
    subject = visual_elements.get('subject_type', '').lower()
    pref_imagery = {i.lower() for i in visual_prefs.get('imagery', [])}
    if subject and pref_imagery:
        components += 1
        # Check for related terms
        subject_groups = {
            'human_face': {'human_faces', 'human_centered', 'emotional_moments', 'close_ups', 'diverse_faces'},
            'group': {'group_photos', 'community_events', 'diverse_faces'},
            'data': {'infographics', 'data_visualizations', 'before_after'},
            'landscape': {'heritage', 'generational', 'institutional'},
            'action': {'dynamic', 'raw', 'authentic', 'user_generated'},
        }
        matched = False
        for group_terms in subject_groups.values():
            if subject in group_terms and group_terms & pref_imagery:
                matched = True
                break
        if subject in pref_imagery:
            matched = True
        score += 1.0 if matched else 0.3

    # Style match
    content_style = visual_elements.get('style', '').lower() if 'style' in visual_elements else ''
    pref_style = visual_prefs.get('style', '').lower()
    if content_style and pref_style:
        components += 1
        score += 1.0 if content_style == pref_style else 0.4

    if components > 0:
        return max(0.0, min(1.0, score / components))
    return 0.5


def _score_image_alignment(visual_elements, audience_appeal, persona):
    """Score overall image alignment with persona."""
    visual_score = _score_visual_match(visual_elements, persona.get('visual_preferences', {}))

    # Audience appeal is a bonus factor
    audience_bonus = 0.0
    if audience_appeal:
        # If the image targets the right demographic, slight boost
        audience_bonus = 0.1

    return max(0.0, min(1.0, visual_score + audience_bonus))


def _score_coherence(copy_data, image_data):
    """Score how well copy and image work together."""
    copy_emotion = copy_data.get('emotional_tone', {}).get('primary', '')
    image_emotion = image_data.get('emotional_tone', {}).get('primary', '')

    if copy_emotion and image_emotion:
        if copy_emotion.lower() == image_emotion.lower():
            return 0.9
        # Check if they're in the same emotional family
        emotion_families = [
            {'compassion', 'empathy', 'warmth', 'caring', 'hope'},
            {'urgency', 'justice', 'outrage', 'change'},
            {'pride', 'achievement', 'progress', 'success'},
            {'belonging', 'community', 'togetherness', 'solidarity'},
        ]
        for family in emotion_families:
            if copy_emotion.lower() in family and image_emotion.lower() in family:
                return 0.75
        return 0.5
    return 0.6


def _calculate_overall(scores, asset_type):
    """Calculate weighted overall score."""
    if asset_type == 'copy':
        weights = {
            'emotional_impact': 0.30,
            'clarity': 0.20,
            'persona_alignment': 0.30,
            'cta_effectiveness': 0.15,
            'channel_fit': 0.05,
        }
    elif asset_type == 'image':
        weights = {
            'emotional_impact': 0.30,
            'visual_appeal': 0.25,
            'persona_alignment': 0.25,
            'brand_consistency': 0.15,
            'channel_fit': 0.05,
        }
    else:  # campaign
        weights = {
            'emotional_impact': 0.25,
            'persona_alignment': 0.25,
            'coherence': 0.20,
            'channel_fit': 0.05,
        }
        # Add remaining scores with equal small weights
        remaining = {k: v for k, v in scores.items()
                     if k not in weights and k != 'overall'}
        if remaining:
            remaining_weight = 0.25 / len(remaining)
            for k in remaining:
                weights[k] = remaining_weight

    total = 0.0
    weight_sum = 0.0
    for key, weight in weights.items():
        if key in scores:
            total += scores[key] * weight
            weight_sum += weight

    if weight_sum > 0:
        return total / weight_sum
    return 0.5


def _avg(values):
    """Average a list of values."""
    if not values:
        return 0.5
    return sum(values) / len(values)
