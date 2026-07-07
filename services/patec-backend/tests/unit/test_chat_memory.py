from app.services.chat_memory import should_retrieve_chat_memory


def test_should_retrieve_chat_memory_for_explicit_history_requests():
    assert should_retrieve_chat_memory(
        "JULIA, consulte o histórico antigo sobre a válvula XV-102"
    )
    assert should_retrieve_chat_memory(
        "Você lembra o que falamos antes sobre redundância?"
    )
    assert should_retrieve_chat_memory(
        "Procure na conversa aquela decisão anterior"
    )


def test_should_not_retrieve_chat_memory_for_regular_messages():
    assert not should_retrieve_chat_memory(
        "Avalie se este item pode ser aceito com comentário"
    )
    assert not should_retrieve_chat_memory(
        "Abra a tabela do caso para eu revisar os requisitos"
    )
