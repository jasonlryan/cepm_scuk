"""
Recommendation engine for CEPM.

Generates actionable suggestions based on scores and persona
to help charities improve their marketing assets.
"""


def generate_recommendations(scores, analysis_data, persona, asset_type, user_context=None):
    """
    Generate recommendations based on scores and persona.

    Returns a list of recommendation dicts with:
        aspect, suggestion, importance (high/medium/low), current_score
    """
    recommendations = []
    persona_name = persona.get('name', 'target persona')
    channel = (user_context or {}).get('channel', '')
    campaign_goal = (user_context or {}).get('campaign_goal', '')

    if asset_type in ('copy', 'campaign'):
        recommendations.extend(
            _copy_recommendations(scores, analysis_data, persona, persona_name, campaign_goal)
        )

    if asset_type in ('image', 'campaign'):
        image_data = analysis_data if asset_type == 'image' else analysis_data.get('image_analysis', {})
        recommendations.extend(
            _image_recommendations(scores, image_data, persona, persona_name)
        )

    if asset_type == 'campaign':
        recommendations.extend(
            _campaign_recommendations(scores, analysis_data, persona_name)
        )

    # Channel-specific recommendations
    if scores.get('channel_fit', 1.0) < 0.6 and channel:
        preferred = persona.get('preferred_channels', [])
        recommendations.append({
            'aspect': 'channel_strategy',
            'suggestion': f'This {channel} content may not be optimal for {persona_name}. '
                          f'Consider prioritising: {", ".join(preferred)}.',
            'importance': 'medium',
            'current_score': scores.get('channel_fit', 0.4)
        })

    # Sort by importance and score (worst scores first)
    importance_order = {'high': 0, 'medium': 1, 'low': 2}
    recommendations.sort(key=lambda r: (importance_order.get(r['importance'], 1), r['current_score']))

    return recommendations


def generate_persona_insights(scores, persona):
    """Generate strengths and weaknesses relative to the persona."""
    strengths = []
    weaknesses = []

    threshold_high = 0.7
    threshold_low = 0.5

    score_labels = {
        'emotional_impact': 'Emotional connection',
        'clarity': 'Message clarity',
        'persona_alignment': 'Persona alignment',
        'cta_effectiveness': 'Call-to-action effectiveness',
        'visual_appeal': 'Visual appeal',
        'brand_consistency': 'Brand consistency',
        'channel_fit': 'Channel fit',
        'coherence': 'Copy-image coherence',
    }

    for key, label in score_labels.items():
        if key in scores and key != 'overall':
            if scores[key] >= threshold_high:
                strengths.append(label)
            elif scores[key] < threshold_low:
                weaknesses.append(label)

    return {
        'strengths': strengths or ['No standout strengths identified'],
        'weaknesses': weaknesses or ['No major weaknesses identified'],
        'top_priority': weaknesses[0] if weaknesses else 'Continue current approach'
    }


def _copy_recommendations(scores, analysis_data, persona, persona_name, campaign_goal):
    """Generate recommendations for copy assets."""
    recs = []
    triggers = persona.get('emotional_triggers', [])
    comm_prefs = persona.get('communication_preferences', {})
    response_patterns = persona.get('response_patterns', {})

    # Emotional impact
    emotional_score = scores.get('emotional_impact', scores.get('copy_emotional_impact', 0.5))
    if emotional_score < 0.6:
        top_triggers = ', '.join(triggers[:3])
        recs.append({
            'aspect': 'emotional_tone',
            'suggestion': f'Strengthen emotional resonance for {persona_name}. '
                          f'Lean into themes of {top_triggers}. '
                          f'The current emotional tone doesn\'t strongly connect with this persona\'s triggers.',
            'importance': 'high',
            'current_score': emotional_score
        })
    elif emotional_score < 0.75:
        recs.append({
            'aspect': 'emotional_tone',
            'suggestion': f'Good emotional connection, but could be stronger. '
                          f'Consider more vivid language around {triggers[0] if triggers else "key themes"} '
                          f'to deepen the emotional response.',
            'importance': 'medium',
            'current_score': emotional_score
        })

    # Clarity
    clarity_score = scores.get('clarity', scores.get('copy_clarity', 0.5))
    pref_formality = comm_prefs.get('formality', 0.5)
    pref_length = comm_prefs.get('message_length', 'medium')

    if clarity_score < 0.5:
        if pref_formality < 0.4:
            recs.append({
                'aspect': 'readability',
                'suggestion': f'{persona_name} prefers simple, accessible language. '
                              f'Simplify sentence structure and use everyday words. '
                              f'Aim for shorter paragraphs and a {pref_length}-length message.',
                'importance': 'high',
                'current_score': clarity_score
            })
        else:
            recs.append({
                'aspect': 'readability',
                'suggestion': f'The complexity level doesn\'t match {persona_name}\'s preferences. '
                              f'This persona expects a more {comm_prefs.get("tone", "balanced")} tone '
                              f'with {pref_length} message length.',
                'importance': 'high',
                'current_score': clarity_score
            })
    elif clarity_score < 0.7:
        recs.append({
            'aspect': 'readability',
            'suggestion': f'Readability is adequate but could better match {persona_name}\'s '
                          f'preference for {pref_length}, {comm_prefs.get("tone", "balanced")} communication.',
            'importance': 'low',
            'current_score': clarity_score
        })

    # Persona alignment
    alignment_score = scores.get('persona_alignment', scores.get('copy_persona_alignment', 0.5))
    if alignment_score < 0.6:
        pref_lang = comm_prefs.get('preferred_language', [])
        recs.append({
            'aspect': 'persona_alignment',
            'suggestion': f'The overall tone and messaging don\'t strongly align with {persona_name}. '
                          f'Try using more {", ".join(pref_lang[:3])} language '
                          f'that speaks to their motivation of {persona.get("donation_motivations", ["giving"])[0]}.',
            'importance': 'high',
            'current_score': alignment_score
        })

    # CTA effectiveness
    cta_score = scores.get('cta_effectiveness', scores.get('copy_cta_effectiveness', 0.5))
    if cta_score < 0.6:
        if response_patterns.get('urgency_sensitivity', 0.5) > 0.7:
            recs.append({
                'aspect': 'call_to_action',
                'suggestion': f'{persona_name} responds well to urgency. '
                              f'Add time-sensitive language and make the ask more immediate and specific.',
                'importance': 'high',
                'current_score': cta_score
            })
        elif response_patterns.get('data_driven', 0.5) > 0.7:
            recs.append({
                'aspect': 'call_to_action',
                'suggestion': f'{persona_name} is data-driven. '
                              f'Include specific numbers, impact metrics, or social proof in your CTA '
                              f'to make the case for action.',
                'importance': 'high',
                'current_score': cta_score
            })
        else:
            recs.append({
                'aspect': 'call_to_action',
                'suggestion': f'The call-to-action could be stronger for {persona_name}. '
                              f'Make it clearer what you want them to do and why it matters to them.',
                'importance': 'medium',
                'current_score': cta_score
            })

    # Campaign goal specific
    if campaign_goal == 'fundraising' and cta_score < 0.7:
        recs.append({
            'aspect': 'fundraising_ask',
            'suggestion': 'For a fundraising campaign, the donation ask should be prominent and specific. '
                          'Consider suggesting a concrete amount or showing exactly what a donation achieves.',
            'importance': 'medium',
            'current_score': cta_score
        })
    elif campaign_goal == 'awareness' and emotional_score < 0.7:
        recs.append({
            'aspect': 'awareness_impact',
            'suggestion': 'Awareness campaigns need strong emotional hooks to be memorable. '
                          'Consider a more provocative or surprising angle to cut through noise.',
            'importance': 'medium',
            'current_score': emotional_score
        })

    return recs


def _image_recommendations(scores, image_data, persona, persona_name):
    """Generate recommendations for image assets."""
    recs = []
    visual_prefs = persona.get('visual_preferences', {})

    # Visual appeal
    visual_score = scores.get('visual_appeal', scores.get('image_visual_appeal', 0.5))
    if visual_score < 0.6:
        pref_colors = visual_prefs.get('colors', [])
        pref_imagery = visual_prefs.get('imagery', [])
        pref_style = visual_prefs.get('style', '')
        recs.append({
            'aspect': 'visual_style',
            'suggestion': f'{persona_name} responds best to {pref_style} imagery '
                          f'with {", ".join(pref_colors[:2])} colours and {", ".join(pref_imagery[:2])} subjects. '
                          f'Consider adjusting the visual approach to better match these preferences.',
            'importance': 'high',
            'current_score': visual_score
        })

    # Emotional impact from image
    emotional_score = scores.get('emotional_impact', scores.get('image_emotional_impact', 0.5))
    if emotional_score < 0.6:
        triggers = persona.get('emotional_triggers', [])
        recs.append({
            'aspect': 'image_emotion',
            'suggestion': f'The image doesn\'t strongly evoke the emotions that resonate with {persona_name} '
                          f'({", ".join(triggers[:3])}). Consider imagery that more directly triggers '
                          f'these emotional responses.',
            'importance': 'high',
            'current_score': emotional_score
        })

    # Brand consistency
    brand_score = scores.get('brand_consistency', scores.get('image_brand_consistency', 0.5))
    if brand_score < 0.6:
        recs.append({
            'aspect': 'brand_consistency',
            'suggestion': 'The image may not align well with established brand guidelines. '
                          'Ensure visual elements (colours, typography overlay, logo placement) '
                          'are consistent with your charity\'s brand identity.',
            'importance': 'medium',
            'current_score': brand_score
        })

    return recs


def _campaign_recommendations(scores, analysis_data, persona_name):
    """Generate campaign-level recommendations."""
    recs = []

    coherence = scores.get('coherence', 0.5)
    if coherence < 0.7:
        recs.append({
            'aspect': 'campaign_coherence',
            'suggestion': f'The copy and imagery tell different emotional stories. '
                          f'Align the emotional tone across both to create a more cohesive experience '
                          f'for {persona_name}.',
            'importance': 'high',
            'current_score': coherence
        })

    return recs
