<?php 
//MySQL Database Connect 
include 'dbconnect.php'; 

$sch1data = 'SELECT * FROM `settings` WHERE `ID` = 1'; 
  $sch1query = mysqli_query($connection, $sch1data) or die("Couldn't execute query. ". mysql_error()); 
  $sch1data2 = mysqli_fetch_array($sch1query); 
  $sch1endtime = strtotime($sch1data2['endtime']);

$sch2data = 'SELECT * FROM `settings` WHERE `ID` = 2'; 
  $sch2query = mysqli_query($connection, $sch2data) or die("Couldn't execute query. ". mysql_error()); 
  $sch2data2 = mysqli_fetch_array($sch2query); 
  $sch2starttime = strtotime($sch2data2['starttime']);
  $sch2endtime = strtotime($sch2data2['endtime']);
  
$sch3data = 'SELECT * FROM `settings` WHERE `ID` = 3'; 
  $sch3query = mysqli_query($connection, $sch3data) or die("Couldn't execute query. ". mysql_error()); 
  $sch3data2 = mysqli_fetch_array($sch3query); 
  $sch3starttime = strtotime($sch3data2['starttime']);
  $sch3endtime = strtotime($sch3data2['endtime']);

$sch4data = 'SELECT * FROM `settings` WHERE `ID` = 4'; 
  $sch4query = mysqli_query($connection, $sch4data) or die("Couldn't execute query. ". mysql_error()); 
  $sch4data2 = mysqli_fetch_array($sch4query); 
  $sch4starttime = strtotime($sch4data2['starttime']);
?> 
 
 <!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>

<head>
<meta content="en-ca" http-equiv="Content-Language">
<meta content="text/html; charset=utf-8" http-equiv="Content-Type">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Greenhouse Settings</title>
<style type="text/css">
.wrap {
	width:800px;
	margin:0 auto;
	background-color: #ffffff;
	opacity: 0.9;
	border-radius: 25px;
	text-align: center;
}
body {
     background-image: url("/images/greenhousebg4.jpg");
     background-repeat: no-repeat;
     background-position: center top;
	 background-attachment: fixed;
 } 
.auto-style1 {
	text-align: center;
}
</style>
</head>

<body>
<div class="wrap">
<p>&nbsp;</p>
<form name="settings" method="post" action="settingsformsch2.php">
	<table style="width: 800" align="center">
		<tr>
			<td class="auto-style1" style="width: 88px">Start Time</td>
			<td class="auto-style1" style="width: 88px">End Time</td>
			<td class="auto-style1" style="width: 88px">High Temp</td>
			<td class="auto-style1" style="width: 89px">High Temp Range</td>
			<td class="auto-style1" style="width: 89px">Low Temp</td>
			<td class="auto-style1" style="width: 89px">Low Temp Range</td>
			<td class="auto-style1" style="width: 89px">Window Open Temp</td>
			<td class="auto-style1" style="width: 89px">Window Open Temp Range</td>
			<td class="auto-style1" style="width: 89px">Circulation Fan</td>
		</tr>
		<tr>
			<td colspan="9" class="auto-style1">
	<strong>Schedule 1</strong></td>
		</tr>
		<tr>
			<td class="auto-style1" style="width: 88px">00:00</td>
			<td class="auto-style1" style="width: 88">
				<input name="sch1endtimehour" type="text" value="<?php echo date("H", $sch1endtime)?>" style="width: 20px"> :
				<input name="sch1endtimemin" type="text" value="<?php echo date("i", $sch1endtime)?>" style="width: 20px"></td>
			<td class="auto-style1" style="width: 88px">
				<input name="sch1hightemp" type="text" value="<?php echo $sch1data2['hightemp']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<input name="sch1hightemprange" type="text" value="<?php echo $sch1data2['hightemprange']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<input name="sch1lowtemp" type="text" value="<?php echo $sch1data2['lowtemp']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<input name="sch1lowtemprange" type="text" value="<?php echo $sch1data2['lowtemprange']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<input name="sch1windowtemp" type="text" value="<?php echo $sch1data2['windowtemp']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<input name="sch1windowtemprange" type="text" value="<?php echo $sch1data2['windowtemprange']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<select name="sch1circfan">
				<?php
				if ($sch1data2['circfan']==1) {
					echo '<option selected="" value="1">On</option>';
					echo '<option value="0">Off</option>';
				} else if ($sch1data2['circfan']==0){
					echo '<option value="1">On</option>';
					echo '<option selected="" value="0">Off</option>';
				} ?>
				</select></td>
		</tr>
		<tr>
			<td class="auto-style1" style="width: 88px">&nbsp;</td>
			<td class="auto-style1" style="width: 88px">&nbsp;</td>
			<td class="auto-style1" style="width: 88px">&nbsp;</td>
			<td class="auto-style1" style="width: 89px">&nbsp;</td>
			<td class="auto-style1" style="width: 89px">&nbsp;</td>
			<td class="auto-style1" style="width: 89px">&nbsp;</td>
			<td class="auto-style1" style="width: 89px">&nbsp;</td>
			<td class="auto-style1" style="width: 89px">&nbsp;</td>
			<td class="auto-style1" style="width: 89px">&nbsp;</td>
		</tr>
		<tr>
			<td class="auto-style1" colspan="9"><strong>Schedule 2</strong></td>
		</tr>
		<tr>
			<td class="auto-style1" style="width: 88px">
				<input name="sch2starttimehour" type="text" value="<?php echo date("H", $sch2starttime)?>" style="width: 20px"> :
				<input name="sch2starttimemin" type="text" value="<?php echo date("i", $sch2starttime)?>" style="width: 20px"></td>
			<td class="auto-style1" style="width: 88px">
				<input name="sch2endtimehour" type="text" value="<?php echo date("H", $sch2endtime)?>" style="width: 20px"> 
				:
				<input name="sch2endtimemin" type="text" value="<?php echo date("i", $sch2endtime)?>" style="width: 20px"></td>
			<td class="auto-style1" style="width: 88px">
				<input name="sch2hightemp" type="text" value="<?php echo $sch2data2['hightemp']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<input name="sch2hightemprange" type="text" value="<?php echo $sch2data2['hightemprange']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<input name="sch2lowtemp" type="text" value="<?php echo $sch2data2['lowtemp']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<input name="sch2lowtemprange" type="text" value="<?php echo $sch2data2['lowtemprange']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<input name="sch2windowtemp" type="text" value="<?php echo $sch2data2['windowtemp']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<input name="sch2windowtemprange" type="text" value="<?php echo $sch2data2['windowtemprange']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<select name="sch2circfan">
				<?php
				if ($sch2data2['circfan']==1) {
					echo '<option selected="" value="1">On</option>';
					echo '<option value="0">Off</option>';
				} else if ($sch2data2['circfan']==0){
					echo '<option value="1">On</option>';
					echo '<option selected="" value="0">Off</option>';
				} ?>
				</select></td>
		</tr>
		<tr>
			<td class="auto-style1" style="width: 88px">&nbsp;</td>
			<td class="auto-style1" style="width: 88px">&nbsp;</td>
			<td class="auto-style1" style="width: 88px">&nbsp;</td>
			<td class="auto-style1" style="width: 89px">&nbsp;</td>
			<td class="auto-style1" style="width: 89px">&nbsp;</td>
			<td class="auto-style1" style="width: 89px">&nbsp;</td>
			<td class="auto-style1" style="width: 89px">&nbsp;</td>
			<td class="auto-style1" style="width: 89px">&nbsp;</td>
			<td class="auto-style1" style="width: 89px">&nbsp;</td>
		</tr>
		<tr>
			<td class="auto-style1" colspan="9"><strong>Schedule 3</strong></td>
		</tr>
		<tr>
			<td class="auto-style1" style="width: 88px">
				<input name="sch3starttimehour" type="text" value="<?php echo date("H", $sch3starttime)?>" style="width: 20px"> :
				<input name="sch3starttimemin" type="text" value="<?php echo date("i", $sch3starttime)?>" style="width: 20px"></td>
			<td class="auto-style1" style="width: 88px">
				<input name="sch3endtimehour" type="text" value="<?php echo date("H", $sch3endtime)?>" style="width: 20px"> :
				<input name="sch3endtimemin" type="text" value="<?php echo date("i", $sch3endtime)?>" style="width: 20px"></td>
			<td class="auto-style1" style="width: 88px">
				<input name="sch3hightemp" type="text" value="<?php echo $sch3data2['hightemp']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<input name="sch3hightemprange" type="text" value="<?php echo $sch3data2['hightemprange']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<input name="sch3lowtemp" type="text" value="<?php echo $sch3data2['lowtemp']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<input name="sch3lowtemprange" type="text" value="<?php echo $sch3data2['lowtemprange']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<input name="sch3windowtemp" type="text" value="<?php echo $sch3data2['windowtemp']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<input name="sch3windowtemprange" type="text" value="<?php echo $sch3data2['windowtemprange']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<select name="sch3circfan">
				<?php
				if ($sch3data2['circfan']==1) {
					echo '<option selected="" value="1">On</option>';
					echo '<option value="0">Off</option>';
				} else if ($sch3data2['circfan']==0){
					echo '<option value="1">On</option>';
					echo '<option selected="" value="0">Off</option>';
				} ?>
				</select></td>
		</tr>
		<tr>
			<td class="auto-style1" style="width: 88px">&nbsp;</td>
			<td class="auto-style1" style="width: 88px">&nbsp;</td>
			<td class="auto-style1" style="width: 88px">&nbsp;</td>
			<td class="auto-style1" style="width: 89px">&nbsp;</td>
			<td class="auto-style1" style="width: 89px">&nbsp;</td>
			<td class="auto-style1" style="width: 89px">&nbsp;</td>
			<td class="auto-style1" style="width: 89px">&nbsp;</td>
			<td class="auto-style1" style="width: 89px">&nbsp;</td>
			<td class="auto-style1" style="width: 89px">&nbsp;</td>
		</tr>
		<tr>
			<td class="auto-style1" colspan="9"><strong>Schedule 4</strong></td>
		</tr>
		<tr>
			<td class="auto-style1" style="width: 88px">
				<input name="sch4starttimehour" type="text" value="<?php echo date("H", $sch4starttime)?>" style="width: 20px"> 
				:
				<input name="sch4starttimemin" type="text" value="<?php echo date("i", $sch4starttime)?>" style="width: 20px"></td>
			<td class="auto-style1" style="width: 88px">23:59</td>
			<td class="auto-style1" style="width: 88px">
				<input name="sch4hightemp" type="text" value="<?php echo $sch4data2['hightemp']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<input name="sch4hightemprange" type="text" value="<?php echo $sch4data2['hightemprange']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<input name="sch4lowtemp" type="text" value="<?php echo $sch4data2['lowtemp']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<input name="sch4lowtemprange" type="text" value="<?php echo $sch4data2['lowtemprange']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<input name="sch4windowtemp" type="text" value="<?php echo $sch4data2['windowtemp']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<input name="sch4windowtemprange" type="text" value="<?php echo $sch4data2['windowtemprange']?>" style="width: 40px"></td>
			<td class="auto-style1" style="width: 89px">
				<select name="sch4circfan">
				<?php
				if ($sch4data2['circfan']==1) {
					echo '<option selected="" value="1">On</option>';
					echo '<option value="0">Off</option>';
				} else if ($sch4data2['circfan']==0){
					echo '<option value="1">On</option>';
					echo '<option selected="" value="0">Off</option>';
				} ?>
			</select></td>
		
		</tr>
	</table>
	<br>
	<input name="submit" type="submit" value="submit"></form>
<p><a href="index.php">Home</a></p>
<br>
	</div>

</body>

</html>
