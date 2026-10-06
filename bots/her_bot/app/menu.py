from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class Menu:
    def keyboard(self, owner: bool) -> InlineKeyboardMarkup:
        rows = [
            [
                InlineKeyboardButton(
                    text="🕯️ دربارهٔ Her", callback_data="about"
                ),
                InlineKeyboardButton(
                    text="🧹 فراموشی گفتگو", callback_data="forget"
                ),
            ]
        ]
        if owner:
            rows.extend(
                [
                    [
                        InlineKeyboardButton(
                            text="🎧 آرشیو آهنگ", callback_data="tracks"
                        ),
                        InlineKeyboardButton(
                            text="🌙 برنامهٔ امشب", callback_data="plan"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text="🕯️ وضعیت", callback_data="status"
                        ),
                        InlineKeyboardButton(
                            text="⏸ توقف نشر", callback_data="pause"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text="▶️ ادامهٔ نشر", callback_data="resume"
                        )
                    ],
                ]
            )
        rows.append(
            [
                InlineKeyboardButton(
                    text="🎀 برگشت به خانه", callback_data="start"
                )
            ]
        )
        return InlineKeyboardMarkup(inline_keyboard=rows)
