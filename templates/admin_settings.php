<?php
/** @var array $_ */
?>
<div id="group-photo-sorter-admin-settings" class="section">
    <h2>Group Photo Sorter Setup & Diagnostics</h2>
    <p class="settings-hint">Configure and verify system-level dependencies required for background image/video conversion and metadata extraction.</p>

    <div class="setup-diagnostics" style="margin-top: 20px; max-width: 750px;">
        <table class="grid">
            <thead>
                <tr>
                    <th style="width: 30%;">Requirement / Dependency</th>
                    <th style="width: 25%;">Status</th>
                    <th style="width: 45%;">Notes</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><strong>PHP <code>exec()</code> Execution</strong></td>
                    <td>
                        <span class="status-badge <?php echo $_['execEnabled'] ? 'status-ok' : 'status-fail'; ?>">
                            <?php echo $_['execEnabled'] ? 'Enabled' : 'Disabled / Blocked'; ?>
                        </span>
                    </td>
                    <td>Required to execute python converters and spawn background FFmpeg processes. Check your PHP configuration's <code>disable_functions</code>.</td>
                </tr>
                <tr>
                    <td><strong>Python 3 Executable</strong></td>
                    <td>
                        <span class="status-badge <?php echo $_['hasPython'] ? 'status-ok' : 'status-fail'; ?>">
                            <?php echo $_['hasPython'] ? 'Found' : 'Not Found'; ?>
                        </span>
                    </td>
                    <td>Used for image conversion and metadata extraction. Must be available in system <code>PATH</code>.</td>
                </tr>
                <tr>
                    <td><strong>FFmpeg Converter</strong></td>
                    <td>
                        <span class="status-badge <?php echo $_['hasFfmpeg'] ? 'status-ok' : 'status-fail'; ?>">
                            <?php echo $_['hasFfmpeg'] ? 'Found' : 'Not Found'; ?>
                        </span>
                    </td>
                    <td>Required to encode and compress guest video uploads into MP4 format.</td>
                </tr>
                <tr>
                    <td><strong>FFprobe Analyzer</strong></td>
                    <td>
                        <span class="status-badge <?php echo $_['hasFfprobe'] ? 'status-ok' : 'status-fail'; ?>">
                            <?php echo $_['hasFfprobe'] ? 'Found' : 'Not Found'; ?>
                        </span>
                    </td>
                    <td>Required to inspect uploaded video metadata (dimensions and creation dates).</td>
                </tr>
                <tr>
                    <td><strong>Python Libraries</strong></td>
                    <td>
                        <div class="python-libs-list" style="line-height: 1.6;">
                            <div class="lib-status">
                                <code>pillow</code>: <?php echo $_['pythonLibs']['pillow'] ? ' <span class="badge badge-green">OK</span>' : ' <span class="badge badge-red">Missing</span>'; ?>
                            </div>
                            <div class="lib-status">
                                <code>pillow_heif</code>: <?php echo $_['pythonLibs']['pillow_heif'] ? ' <span class="badge badge-green">OK</span>' : ' <span class="badge badge-red">Missing</span> (No HEIC support)'; ?>
                            </div>
                            <div class="lib-status">
                                <code>rawpy</code>: <?php echo $_['pythonLibs']['rawpy'] ? ' <span class="badge badge-green">OK</span>' : ' <span class="badge badge-red">Missing</span> (No RAW camera support)'; ?>
                            </div>
                        </div>
                    </td>
                    <td>
                        Install these packages globally or inside a python virtual environment:
                        <pre style="background: #f1f1f1; padding: 6px; border-radius: 4px; font-size: 0.85em; overflow-x: auto; margin-top: 5px;">python3 -m venv venv
./venv/bin/pip install pillow pillow-heif rawpy</pre>
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
</div>

<style>
    .status-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 0.85em;
        text-align: center;
        min-width: 80px;
    }
    .status-ok { background-color: #e2f0d9; color: #385723; border: 1px solid #c5e0b4; }
    .status-fail { background-color: #fce4d6; color: #c65911; border: 1px solid #f8cbad; }
    
    .badge {
        display: inline-block;
        padding: 1px 6px;
        border-radius: 4px;
        font-size: 0.8em;
        font-weight: bold;
    }
    .badge-green { background-color: #e2f0d9; color: #385723; }
    .badge-red { background-color: #fce4d6; color: #c65911; }

    .setup-diagnostics table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
    .setup-diagnostics th, .setup-diagnostics td { padding: 12px; border: 1px solid #dee2e6; text-align: left; vertical-align: top; }
    .setup-diagnostics th { background-color: #f8f9fa; font-weight: bold; }
    .setup-diagnostics tr:hover { background-color: #fcfcfc; }
</style>
