import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import insert_report_images as inserter
import build_image_insertion_confirmation as confirmation


class ImageCaptionTests(unittest.TestCase):
    def test_generation_note_is_not_used_as_visible_caption(self):
        item = {
            "caption": "目录基础操作（画面不加 AI/示意图标注）",
            "image_purpose": "创建目录、复制 passwd 并检查权限",
            "step_context": "实施阶段第 1 至 3 项：创建目录、复制 passwd，并执行 cp -i。",
        }
        self.assertEqual(inserter.caption_for_item(1, item), "图 1 创建目录、复制 passwd 并检查权限")

    def test_step_range_is_removed_from_fallback_caption(self):
        item = {"step_context": "实施阶段第 9 至 10 项：解压归档并查找 fun 文件。"}
        self.assertEqual(inserter.caption_for_item(4, item), "图 4 解压归档并查找 fun 文件。")

    def test_confirmation_prefers_user_facing_image_purpose(self):
        item = {
            "caption": "目录基础操作（画面不加 AI/示意图标注）",
            "image_purpose": "创建目录、复制 passwd 并检查权限",
        }
        self.assertEqual(confirmation.content_summary(item), "创建目录、复制 passwd 并检查权限")

    def test_table_cell_caption_is_kept_with_its_image(self):
        paragraph = Mock()
        paragraph.runs = []
        cell = Mock()
        row = Mock()
        with patch.object(inserter, "allow_table_row_expand", return_value=({}, {})), \
             patch.object(inserter, "fit_image_size", return_value={"inserted_width_inches": 5.7}), \
             patch.object(inserter, "clear_cell_keep_first_paragraph", return_value=paragraph):
            inserter.add_image_to_cell(cell, row, Path("image.png"), "图 1 示例", {}, clear=True)

        self.assertTrue(paragraph.paragraph_format.keep_together)
        paragraph.add_run.assert_any_call("图 1 示例")
        cell.add_paragraph.assert_not_called()


if __name__ == "__main__":
    unittest.main()
