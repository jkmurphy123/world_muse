from __future__ import annotations

from world_muse.wizards.setting_wizard import SETTING_QUESTIONS, SettingWizardSession


def test_setting_wizard_navigation_and_answer_retention():
    wizard = SettingWizardSession()
    assert wizard.total == 5
    assert wizard.current_question == SETTING_QUESTIONS[0]
    assert wizard.is_first is True
    assert wizard.is_last is False

    wizard.set_current_answer("A quiet frontier world.")
    wizard.next()
    assert wizard.current_question == SETTING_QUESTIONS[1]
    wizard.set_current_answer("A floating city above an endless storm.")
    wizard.prev()
    assert wizard.current_question == SETTING_QUESTIONS[0]
    assert wizard.current_answer == "A quiet frontier world."
    wizard.next()
    assert wizard.current_answer == "A floating city above an endless storm."


def test_setting_wizard_summary_and_detail_map():
    wizard = SettingWizardSession()
    wizard.answers = [
        "The Ashbelt",
        "The Glass Harbor",
        "Memory fades after sunset",
        "A civil split over forbidden archives",
        "Archive keepers could lose all legal standing",
    ]

    summary = wizard.build_summary()
    details = wizard.as_detail_map()

    assert summary == "The Ashbelt"
    assert len(details) == 5
    assert list(details.values())[2] == "Memory fades after sunset"
