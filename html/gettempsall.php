<?php 

//MySQL Database Connect 
include 'dbconnect.php';

$temp1data = 'SELECT * FROM `currenttemp` WHERE `ID` = 1'; 
  $temp1query = mysqli_query($connection, $temp1data) or die("Couldn't execute query. ". mysql_error()); 
  $temp1data2 = mysqli_fetch_array($temp1query); 
   
$temp2data = 'SELECT * FROM `currenttemp` WHERE `ID` = 2'; 
  $temp2query = mysqli_query($connection, $temp2data) or die("Couldn't execute query. ". mysql_error()); 
  $temp2data2 = mysqli_fetch_array($temp2query); 
  
$temp3data = 'SELECT * FROM `currenttemp` WHERE `ID` = 3'; 
  $temp3query = mysqli_query($connection, $temp3data) or die("Couldn't execute query. ". mysql_error()); 
  $temp3data2 = mysqli_fetch_array($temp3query); 

$avgtempdata = 'SELECT * FROM `currenttemp` WHERE `ID` = 5'; 
  $avgtempquery = mysqli_query($connection, $avgtempdata) or die("Couldn't execute query. ". mysql_error()); 
  $avgtempdata2 = mysqli_fetch_array($avgtempquery); 

$woodstovetempdata = 'SELECT * FROM `currenttemp` WHERE `ID` = 6'; 
  $woodstovetempquery = mysqli_query($connection, $woodstovetempdata) or die("Couldn't execute query. ". mysql_error()); 
  $woodstovetempdata2 = mysqli_fetch_array($woodstovetempquery); 
  
  echo json_encode(array($temp1data2['temperature'], $temp1data2['temperatureF'], $temp2data2['temperature'], $temp2data2['temperatureF'], $temp3data2['temperature'], $temp3data2['temperatureF'], $avgtempdata2['temperature'], $avgtempdata2['temperatureF'], $woodstovetempdata2['temperature'], $woodstovetempdata2['temperatureF']));
  
  ?> 
 
 
