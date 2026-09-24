from enum import Enum, StrEnum
from typing import Any, get_args, get_origin

from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QCheckBox, QSizePolicy
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .model import AppSettings


class SettingsManager:
    def load(self) -> AppSettings:  # TODO(TheTimebreaker): implement when ready
        return AppSettings()

    def save(self, settings: AppSettings) -> None: ...


class FieldKind(StrEnum):
    MODEL = "model"
    BOOL = "bool"
    INT = "int"
    FLOAT = "float"
    STR = "str"
    ENUM = "enum"
    SET_ENUM = "set_enum"
    UNKNOWN = "unknown"


class NoWheelSpinBox(QSpinBox):
    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()


class PersistentMenu(QMenu):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._pressed_action = None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        action = self.actionAt(event.position().toPoint())

        if action is not None and action.isCheckable():
            self._pressed_action = action
            event.accept()
            return

        self._pressed_action = None
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        action = self.actionAt(event.position().toPoint())

        if action is not None and action is self._pressed_action and action.isCheckable():
            action.setChecked(not action.isChecked())
            self._pressed_action = None
            event.accept()
            return

        self._pressed_action = None
        super().mouseReleaseEvent(event)


def enum_sort_key(option: Enum) -> object:
    return getattr(option, "sort_key", option.value)


class EnumSetWidget(QPushButton):
    def __init__(
        self,
        enum_type: type[Enum],
        value: set[Enum],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.enum_type = enum_type
        self._value = set(value)

        self.setText(self._button_text())

        self.menu = PersistentMenu(self)

        for option in sorted(enum_type, key=enum_sort_key):
            action = self.menu.addAction(getattr(option, "title", option.name))
            action.setCheckable(True)
            action.setChecked(option in self._value)
            action.toggled.connect(
                lambda checked, option=option: self._set_option(
                    option,
                    checked,
                )
            )

        self.setMenu(self.menu)

    def _set_option(
        self,
        option: Enum,
        checked: bool,
    ) -> None:
        if checked:
            self._value.add(option)
        else:
            self._value.discard(option)

        self.setText(self._button_text())

    def _button_text(self) -> str:
        count = len(self._value)

        if count == 0:
            return "None selected"

        if count == len(self.enum_type):
            return "All selected"

        return f"{count} selected"

    def value(self) -> set[Enum]:
        return set(self._value)


def classify_field(field: FieldInfo) -> FieldKind:
    annotation = field.annotation

    # Nested Pydantic model
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return FieldKind.MODEL

    # Simple scalar types
    if annotation is bool:
        return FieldKind.BOOL

    if annotation is int:
        return FieldKind.INT

    if annotation is float:
        return FieldKind.FLOAT

    if annotation is str:
        return FieldKind.STR

    # Direct enum
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return FieldKind.ENUM

    # Generic/container types
    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is set and len(args) == 1:
        element_type = args[0]

        if isinstance(element_type, type) and issubclass(element_type, Enum):
            return FieldKind.SET_ENUM

    return FieldKind.UNKNOWN


def create_widget(field: Field, value: Any) -> QWidget:
    kind = classify_field(field)

    if kind is FieldKind.BOOL:
        widget = QCheckBox()
        widget.setChecked(value)
        widget.setSizePolicy(
            QSizePolicy.Policy.Maximum,
            QSizePolicy.Policy.Fixed,
        )
        return widget

    if kind is FieldKind.INT:
        widget = NoWheelSpinBox()
        widget.setValue(value)
        widget.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        return widget

    if kind is FieldKind.FLOAT:
        widget = QDoubleSpinBox()
        widget.setValue(value)
        return widget

    if kind is FieldKind.STR:
        widget = QLineEdit()
        widget.setText(value)
        return widget

    if kind is FieldKind.ENUM:
        widget = NoWheelComboBox()
        widget.setFocusPolicy(Qt.FocusPolicy.TabFocus)

        enum_type = field.annotation

        for option in enum_type:
            widget.addItem(
                getattr(option, "title", option.name),
                userData=option,
            )

        widget.setCurrentIndex(widget.findData(value))

        return widget

    if kind is FieldKind.SET_ENUM:
        enum_type = get_args(field.annotation)[0]
        return EnumSetWidget(enum_type, value)

    raise TypeError(f"Don't know how to create a widget for {field.annotation!r}")


class ClickableLabel(QLabel):
    def __init__(
        self,
        text: str,
        target: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.target = target

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.target.setFocus()
        QTest.mouseClick(
            self.target,
            event.button(),
        )
        super().mousePressEvent(event)


class SettingsForm(QWidget):
    def __init__(self, model: BaseModel, parent: QGroupBox | None = None) -> None:
        super().__init__(parent)

        self.model_type = type(model)
        self.widgets: dict[str, QWidget] = {}
        self.child_forms: dict[str, SettingsForm] = {}

        layout = QFormLayout(self)

        for name, field in self.model_type.model_fields.items():
            value = getattr(model, name)
            kind = classify_field(field)

            if kind is FieldKind.MODEL:
                child_form = SettingsForm(value)

                self.child_forms[name] = child_form

                group = QGroupBox(field.title or name)

                group_layout = QFormLayout(group)
                group_layout.addRow(child_form)

                layout.addRow(group)

                continue

            widget = create_widget(field, value)

            label = ClickableLabel(field.title or name, target=widget)

            layout.addRow(label, widget)

            self.widgets[name] = widget

    def _create_model_group(
        self,
        title: str,
        model: BaseModel,
    ) -> QGroupBox:
        group = QGroupBox(title)

        form = SettingsForm(model, group)

        layout = QFormLayout(group)
        layout.addRow(form)

        return group


if __name__ == "__main__":
    app = QApplication([])

    settings = SettingsManager().load()

    window = QMainWindow()
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    form = SettingsForm(settings)
    scroll.setWidget(form)
    window.setCentralWidget(scroll)
    window.resize(800, 600)
    window.show()

    app.exec()
