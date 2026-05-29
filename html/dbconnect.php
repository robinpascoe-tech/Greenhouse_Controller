<?php
// Legacy dashboard connection string.
//
// Production installs should create html/dbconnect.local.php with:
//   $db_host = 'localhost';
//   $db_user = 'greenhouse_app';
//   $db_password = '...';
//   $db_name = 'greenhouse';
//
// dbconnect.local.php is ignored by Git so live credentials are not published
// or overwritten by normal repository updates.
$local_config = __DIR__ . '/dbconnect.local.php';
if (file_exists($local_config)) {
    include $local_config;
} else {
    $db_host = 'localhost';
    $db_user = 'greenhouse_app';
    $db_password = 'change_this_password';
    $db_name = 'greenhouse';
}

$connection = mysqli_connect($db_host, $db_user, $db_password, $db_name) or die ("Couldn't connect to server.");
?>
