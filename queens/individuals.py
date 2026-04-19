from .base import Queen

def get_queen_class(number):
    """Возвращает класс Queen{number}, создавая его при необходимости."""
    class_name = f"Queen{number}"
    # Если класс уже существует в глобальной области видимости, возвращаем его
    if class_name in globals():
        return globals()[class_name]
    # Иначе создаём динамически
    new_class = type(class_name, (Queen,), {})
    globals()[class_name] = new_class
    return new_class