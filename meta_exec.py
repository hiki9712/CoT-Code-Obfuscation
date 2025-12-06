import os
import shutil


def rename_metadata_to_small():
    """
    遍历当前目录下所有文件夹，将其中的 metadata.json 文件重命名为 small.json
    包含文件存在检测、覆盖提示和异常处理
    """
    # 获取当前工作目录
    current_dir = os.getcwd() + "/prevrun"
    print(f"正在扫描当前目录: {current_dir}")

    # 统计变量
    total_folders = 0
    renamed_count = 0
    skipped_count = 0
    error_count = 0

    # 遍历当前目录下的所有条目
    for item in os.listdir(current_dir):
        item_path = os.path.join(current_dir, item)

        # 只处理文件夹
        if os.path.isdir(item_path):
            total_folders += 1
            # 源文件路径（metadata.json）
            src_file = os.path.join(item_path, "metadata.json")
            # 目标文件路径（small.json）
            dst_file = os.path.join(item_path, "small.json")

            try:
                # 检查源文件是否存在
                if os.path.exists(src_file):
                    # 检查目标文件是否已存在
                    if os.path.exists(dst_file):
                        # 提示用户是否覆盖
                        choice = input(f"\n警告：{dst_file} 已存在！是否覆盖？(y/n，默认n) ")
                        if choice.lower() == "y":
                            # 覆盖已存在的文件
                            os.remove(dst_file)  # 先删除目标文件
                            shutil.move(src_file, dst_file)
                            print(f"✅ 已覆盖：{src_file} -> {dst_file}")
                            renamed_count += 1
                        else:
                            print(f"⏭️  已跳过：{src_file}（目标文件已存在）")
                            skipped_count += 1
                    else:
                        # 目标文件不存在，直接重命名
                        shutil.move(src_file, dst_file)
                        print(f"✅ 已重命名：{src_file} -> {dst_file}")
                        renamed_count += 1
                else:
                    # 源文件不存在，跳过
                    print(f"ℹ️  已跳过：{item_path}（未找到 metadata.json）")
                    skipped_count += 1

            except PermissionError:
                print(f"❌ 权限错误：无法操作 {src_file}（可能没有读写权限）")
                error_count += 1
            except Exception as e:
                print(f"❌ 错误：处理 {src_file} 时出现异常 - {str(e)}")
                error_count += 1

    # 输出统计结果
    print("\n" + "=" * 50)
    print(f"📊 处理统计：")
    print(f"总文件夹数：{total_folders}")
    print(f"成功重命名：{renamed_count} 个文件")
    print(f"已跳过文件：{skipped_count} 个（不存在或已存在目标文件）")
    print(f"处理失败：{error_count} 个文件")
    print("=" * 50)


# 使用示例
if __name__ == "__main__":
    rename_metadata_to_small()