<?php
//MySQL Database Connect 
include 'dbconnect.php'; 

$data = "UPDATE `overrides` SET fanoverride='0', fanexpire='2010-01-01 00:00:00' WHERE ID='1'"; 
  $query = mysqli_query($connection, $data) or die("Couldn't execute query. ". mysql_error()); 
?>
