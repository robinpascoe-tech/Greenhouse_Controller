<?php
// Legacy dashboard connection string.
// Replace the placeholder credentials before using this PHP dashboard.
$connection = mysqli_connect('localhost','greenhouse_app','change_this_password') or die ("Couldn't connect to server.");  
$db = mysqli_select_db($connection, 'greenhouse') or die ("Couldn't select database.");  
?>
