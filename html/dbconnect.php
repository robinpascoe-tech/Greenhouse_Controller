<?php
//DB Connection Strings
$connection = mysqli_connect('localhost','root','change_this_password') or die ("Couldn't connect to server.");  
$db = mysqli_select_db($connection, 'greenhouse') or die ("Couldn't select database.");  
?>
