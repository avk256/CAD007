from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate


def test_literal_system_message_does_not_create_json_variables():
    system_text = 'Write JSON like {"success": true, "notes": []}.'
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=system_text),
        ("human", "VALUE: {value}"),
    ])

    assert prompt.input_variables == ["value"]
    rendered = prompt.format_messages(value="ok")
    assert '{"success": true, "notes": []}' in rendered[0].content
