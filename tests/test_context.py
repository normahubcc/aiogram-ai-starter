"""Tests for ConversationManager and sliding window memory."""

from bot.utils.context import ConversationManager


def test_context_initialization():
    """Test initial default values for newly seen users."""
    manager = ConversationManager(
        default_model="deepseek-v4.1-flash",
        default_system_prompt="Custom System Prompt",
        max_turns=3,
    )
    user_id = 42

    assert manager.get_model(user_id) == "deepseek-v4.1-flash"
    assert manager.get_turns_count(user_id) == 0

    messages = manager.get_messages(user_id)
    assert len(messages) == 1
    assert messages[0] == {"role": "system", "content": "Custom System Prompt"}


def test_context_add_turns():
    """Test message addition and retrieval."""
    manager = ConversationManager()
    user_id = 101

    manager.add_user_message(user_id, "Привет")
    manager.add_assistant_message(user_id, "Здравствуйте! Чем могу помочь?")

    messages = manager.get_messages(user_id)
    assert len(messages) == 3
    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "Привет"}
    assert messages[2] == {"role": "assistant", "content": "Здравствуйте! Чем могу помочь?"}
    assert manager.get_turns_count(user_id) == 2


def test_context_sliding_window():
    """Test that context respects max_turns and trims older messages."""
    max_turns = 2  # Total 4 messages max (user + assistant)
    manager = ConversationManager(max_turns=max_turns)
    user_id = 777

    # Add 4 turns (8 messages)
    for i in range(1, 5):
        manager.add_user_message(user_id, f"Вопрос {i}")
        manager.add_assistant_message(user_id, f"Ответ {i}")

    messages = manager.get_messages(user_id)
    # 1 system + 4 recent messages (Вопрос 3, Ответ 3, Вопрос 4, Ответ 4)
    assert len(messages) == 5
    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "Вопрос 3"}
    assert messages[2] == {"role": "assistant", "content": "Ответ 3"}
    assert messages[3] == {"role": "user", "content": "Вопрос 4"}
    assert messages[4] == {"role": "assistant", "content": "Ответ 4"}


def test_context_clear():
    """Test /clear functionality resetting history while preserving model preference."""
    manager = ConversationManager()
    user_id = 555

    manager.set_model(user_id, "claude-sonnet-5-5")
    manager.add_user_message(user_id, "Тестовый вопрос")
    manager.add_assistant_message(user_id, "Тестовый ответ")

    assert manager.get_turns_count(user_id) == 2
    manager.clear(user_id)

    assert manager.get_turns_count(user_id) == 0
    # Model preference should NOT be lost after /clear
    assert manager.get_model(user_id) == "claude-sonnet-5-5"
    # System prompt remains in message list
    messages = manager.get_messages(user_id)
    assert len(messages) == 1
    assert messages[0]["role"] == "system"


def test_context_user_isolation():
    """Test that multiple users have completely isolated state."""
    manager = ConversationManager()
    user_a = 1
    user_b = 2

    manager.set_model(user_a, "claude-sonnet-5-5")
    manager.add_user_message(user_a, "Запрос от пользователя А")

    assert manager.get_model(user_b) == "deepseek-v4.1-flash"
    assert manager.get_turns_count(user_b) == 0
