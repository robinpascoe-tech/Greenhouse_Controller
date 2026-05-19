<?php 

//MySQL Database Connect 
include 'dbconnect.php';

$avgtempdata = 'SELECT * FROM `currenttemp` WHERE `ID` = 5'; 
  $avgtempquery = mysqli_query($connection, $avgtempdata) or die("Couldn't execute query. ". mysql_error()); 
  $avgtempdata2 = mysqli_fetch_array($avgtempquery); 
  
$temp3data = 'SELECT * FROM `currenttemp` WHERE `ID` = 3'; 
  $temp3query = mysqli_query($connection, $temp3data) or die("Couldn't execute query. ". mysql_error()); 
  $temp3data2 = mysqli_fetch_array($temp3query); 

  echo json_encode(array($avgtempdata2['temperature'], $avgtempdata2['temperatureF'], $temp3data2['temperature'], $temp3data2['temperatureF']));
  
  ?> 
 
 
