// 防止 Windows 上出現命令列視窗
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    game_bot_lib::run()
}
