async def loading(c):
    """Compatibility no-op.

    Button loading is handled globally by bot.py by changing the pressed
    inline button text to `⏳ Loading…`. This function intentionally does not
    call CallbackQuery.answer(), so no floating/loading alert is shown.
    """
    return None
