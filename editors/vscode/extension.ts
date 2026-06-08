/* Moss VS Code Extension — v0.31.0
 *
 * Provides Moss language support via moss-lsp and one-click Trust verification.
 * Startup: activates when a .moss file is opened.
 *
 * Commands:
 *   moss.trust    — runs `moss trust --json` on the current file, shows results
 *   moss.run      — runs `moss run` on the current file in the terminal
 */

import * as vscode from 'vscode';
import * as cp from 'child_process';

let statusBarItem: vscode.StatusBarItem;

export function activate(context: vscode.ExtensionContext) {
    // Status bar trust indicator
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.command = 'moss.trust';
    statusBarItem.text = '$(shield) Moss Trust';
    statusBarItem.tooltip = 'Click to verify with moss trust';
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);

    // Trust command
    context.subscriptions.push(
        vscode.commands.registerCommand('moss.trust', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;

            const filePath = editor.document.uri.fsPath;
            statusBarItem.text = '$(sync~spin) Trusting...';
            statusBarItem.backgroundColor = undefined;

            try {
                const result = await runCommand('moss', ['trust', filePath]);
                if (result.exitCode === 0) {
                    statusBarItem.text = '$(pass-filled) Moss Trusted';
                    statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
                    vscode.window.showInformationMessage('Moss Trust: All gates passed');
                } else {
                    statusBarItem.text = '$(error) Trust Failed';
                    statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
                    vscode.window.showErrorMessage('Moss Trust failed. See diagnostics.', 'Show Output')
                        .then(choice => {
                            if (choice === 'Show Output') showOutput(result.stdout + result.stderr);
                        });
                }
            } catch {
                statusBarItem.text = '$(warning) Moss not found';
                statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
            }
        })
    );

    // Run command
    context.subscriptions.push(
        vscode.commands.registerCommand('moss.run', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            const filePath = editor.document.uri.fsPath;
            const terminal = vscode.window.createTerminal('Moss');
            terminal.sendText(`moss run "${filePath}"`);
            terminal.show();
        })
    );
}

function runCommand(cmd: string, args: string[]): Promise<{ exitCode: number; stdout: string; stderr: string }> {
    return new Promise((resolve, reject) => {
        const proc = cp.spawn(cmd, args, { timeout: 30000 });
        let stdout = '';
        let stderr = '';
        proc.stdout?.on('data', (d: Buffer) => stdout += d.toString());
        proc.stderr?.on('data', (d: Buffer) => stderr += d.toString());
        proc.on('close', (code) => resolve({ exitCode: code || 0, stdout, stderr }));
        proc.on('error', reject);
    });
}

function showOutput(text: string) {
    const channel = vscode.window.createOutputChannel('Moss Trust');
    channel.append(text);
    channel.show();
}

export function deactivate() {
    statusBarItem?.dispose();
}
