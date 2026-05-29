<?php 

$sch1endtimehour=$_POST['sch1endtimehour']; 
$sch1endtimemin=$_POST['sch1endtimemin']; 
$sch1hightemp=$_POST['sch1hightemp']; 
$sch1hightemprange=$_POST['sch1hightemprange']; 
$sch1lowtemp=$_POST['sch1lowtemp']; 
$sch1lowtemprange=$_POST['sch1lowtemprange']; 
$sch1windowtemp=$_POST['sch1windowtemp']; 
$sch1windowtemprange=$_POST['sch1windowtemprange']; 
$sch1circfan=$_POST['sch1circfan']; 

$sch2starttimehour=$_POST['sch2starttimehour']; 
$sch2starttimemin=$_POST['sch2starttimemin']; 
$sch2endtimehour=$_POST['sch2endtimehour']; 
$sch2endtimemin=$_POST['sch2endtimemin']; 
$sch2hightemp=$_POST['sch2hightemp']; 
$sch2hightemprange=$_POST['sch2hightemprange']; 
$sch2lowtemp=$_POST['sch2lowtemp']; 
$sch2lowtemprange=$_POST['sch2lowtemprange']; 
$sch2windowtemp=$_POST['sch2windowtemp']; 
$sch2windowtemprange=$_POST['sch2windowtemprange']; 
$sch2circfan=$_POST['sch2circfan']; 

$sch3starttimehour=$_POST['sch3starttimehour']; 
$sch3starttimemin=$_POST['sch3starttimemin']; 
$sch3endtimehour=$_POST['sch3endtimehour']; 
$sch3endtimemin=$_POST['sch3endtimemin']; 
$sch3hightemp=$_POST['sch3hightemp']; 
$sch3hightemprange=$_POST['sch3hightemprange']; 
$sch3lowtemp=$_POST['sch3lowtemp']; 
$sch3lowtemprange=$_POST['sch3lowtemprange']; 
$sch3windowtemp=$_POST['sch3windowtemp']; 
$sch3windowtemprange=$_POST['sch3windowtemprange']; 
$sch3circfan=$_POST['sch3circfan']; 

$sch4starttimehour=$_POST['sch4starttimehour']; 
$sch4starttimemin=$_POST['sch4starttimemin']; 
$sch4hightemp=$_POST['sch4hightemp']; 
$sch4hightemprange=$_POST['sch4hightemprange']; 
$sch4lowtemp=$_POST['sch4lowtemp']; 
$sch4lowtemprange=$_POST['sch4lowtemprange']; 
$sch4windowtemp=$_POST['sch4windowtemp']; 
$sch4windowtemprange=$_POST['sch4windowtemprange']; 
$sch4circfan=$_POST['sch4circfan']; 

$nowtime = date("G:i:s");

$sch1starttime=strtotime("00:00:00");
$sch1endtimestr=$sch1endtimehour . ":" . $sch1endtimemin . ":59";
$sch1endtime=strtotime($sch1endtimestr);

$sch2starttimestr=$sch2starttimehour . ":" . $sch2starttimemin . ":00";
$sch2starttime=strtotime($sch2starttimestr);
$sch2endtimestr=$sch2endtimehour . ":" . $sch2endtimemin . ":59";
$sch2endtime=strtotime($sch2endtimestr);

$sch3starttimestr=$sch3starttimehour . ":" . $sch3starttimemin . ":00";
$sch3starttime=strtotime($sch3starttimestr);
$sch3endtimestr=$sch3endtimehour . ":" . $sch3endtimemin . ":59";
$sch3endtime=strtotime($sch3endtimestr);

$sch4starttimestr=$sch4starttimehour . ":" . $sch4starttimemin . ":00";
$sch4starttime=strtotime($sch4starttimestr);
$sch4endtime=strtotime("23:59:59");

$diff1 = $sch2starttime - $sch1endtime;
$diff2 = $sch3starttime - $sch2endtime;
$diff3 = $sch4starttime - $sch3endtime;


$isformerror = 0;
$formerror = "";

if (empty($sch1hightemp) || empty($sch2hightemp) || empty($sch3hightemp) || empty($sch4hightemp))  {
		$formerror="High Temp is Blank";
		$isformerror=1;
} elseif ($sch1hightemp >= 45 || $sch2hightemp >= 45 || $sch3hightemp >= 45 || $sch4hightemp >=45) {
		$formerror="High Temp is Too high - must be under 45*C";
		$isformerror=1;
} elseif ($sch1hightemp <= 15 || $sch2hightemp <= 15 || $sch3hightemp <= 15 || $sch4hightemp <= 15) {
		$formerror="High Temp is too low - must be above 15*C";
		$isformerror=1;
}

if (empty($sch1hightemprange) || empty($sch2hightemprange) || empty($sch3hightemprange) || empty($sch4hightemprange))  {
		$formerror="High Temp Range is Blank";
		$isformerror=1;
} elseif ($sch1hightemprange >= 11 || $sch2hightemprange >= 11 || $sch3hightemprange >= 11 || $sch4hightemprange >= 11) {
		$formerror="High Temp Range is too Large must be less than 11";
		$isformerror=1;
} elseif ($sch1hightemprange < 1 || $sch2hightemprange < 1 || $sch3hightemprange < 1 || $sch4hightemprange < 1) {
		$formerror="High Temp Range is too small must be at least 1";
		$isformerror=1;
}

if (empty($sch1lowtemp) || empty($sch2lowtemp) || empty($sch3lowtemp) || empty($sch4lowtemp))  {
		$formerror="Low Temp is Blank";
		$isformerror=1;
} elseif ($sch1lowtemp >= 20 || $sch2lowtemp >= 20 || $sch3lowtemp >= 20 || $sch4lowtemp >= 20) {
		$formerror="Low Temp is Too high - must be under 20*C";
		$isformerror=1;
} elseif ($sch1lowtemp <= 1 || $sch2lowtemp <= 1 || $sch3lowtemp <= 1 || $sch4lowtemp <= 1) {
		$formerror="Low Temp is too low - must be above 1*C";
		$isformerror=1;
}

if (empty($sch1lowtemprange) || empty($sch2lowtemprange) || empty($sch3lowtemprange) || empty($sch4lowtemprange))  {
		$formerror="Low Temp Range is Blank";
		$isformerror=1;
} elseif ($sch1lowtemprange >= 11 || $sch2lowtemprange >= 11 || $sch3lowtemprange >= 11 || $sch4lowtemprange >= 11) {
		$formerror="Low Temp Range is too Large must be less than 11";
		$isformerror=1;
} elseif ($sch1lowtemprange < 1 || $sch2lowtemprange < 1 || $sch3lowtemprange < 1 || $sch4lowtemprange < 1) {
		$formerror="Low Temp Range is too small must be at least 1";
		$isformerror=1;
}

if (empty($sch1windowtemp) || empty($sch2windowtemp) || empty($sch3windowtemp) || empty($sch4windowtemp))  {
		$formerror="Window Temp is Blank";
		$isformerror=1;
} elseif ($sch1windowtemp >= 50 || $sch2windowtemp >= 50 || $sch3windowtemp >= 50 || $sch4windowtemp >= 50) {
		$formerror="Window Temp is Too high - must be under 50*C";
		$isformerror=1;
} elseif ($sch1windowtemp <= 15 || $sch2windowtemp <= 15 || $sch3windowtemp <= 15 || $sch4windowtemp <= 15) {
		$formerror="Window Temp is too low - must be above 15*C";
		$isformerror=1;
}

if (empty($sch1windowtemprange) || empty($sch2windowtemprange) || empty($sch3windowtemprange) || empty($sch4windowtemprange))  {
		$formerror="Window Temp Range is Blank";
		$isformerror=1;
} elseif ($sch1windowtemprange >= 11 || $sch2windowtemprange >= 11 || $sch3windowtemprange >= 11 || $sch4windowtemprange >= 11) {
		$formerror="Window Temp Range is too Large must be less than 11";
		$isformerror=1;
} elseif ($sch1windowtemprange <= 2 || $sch2windowtemprange <= 2 || $sch3windowtemprange <= 2 || $sch2windowtemprange <= 2) {
		$formerror="Window Temp Range is too small must be over 2";
		$isformerror=1;
}

if ($sch1starttime < $sch1endtime && $sch1endtime < $sch2starttime && $sch2starttime < $sch2endtime && $sch2endtime < $sch3starttime && $sch3starttime < $sch3endtime && $sch3endtime < $sch4starttime && $sch4starttime < $sch4endtime) {
	//schedule seems logical
} else {
		$formerror="Start and end times are overlapping in schedule.";
		$isformerror=1;
}

if ($diff1 <= 1 && $diff2 <= 1 && $diff3 <= 1) {
	//no gaps in schedule.
} else {
		$formerror="There is a gap in the schedule end and start times.";
		$isformerror=1;	
}

if ($isformerror ==0) {
//MySQL Database Connect 
include 'dbconnect.php'; 

$data1 = "UPDATE `settings` SET endtime='$sch1endtimestr', hightemp='$sch1hightemp', hightemprange='$sch1hightemprange', lowtemp='$sch1lowtemp', lowtemprange='$sch1lowtemprange', windowtemp='$sch1windowtemp', windowtemprange='$sch1windowtemprange', circfan='$sch1circfan'  WHERE ID='1'"; 
  $query1 = mysqli_query($connection, $data1) or die("Couldn't execute query. ". mysql_error()); 
 
 $data2 = "UPDATE `settings` SET starttime='$sch2starttimestr', endtime='$sch2endtimestr', hightemp='$sch2hightemp', hightemprange='$sch2hightemprange', lowtemp='$sch2lowtemp', lowtemprange='$sch2lowtemprange', windowtemp='$sch2windowtemp', windowtemprange='$sch2windowtemprange', circfan='$sch2circfan'  WHERE ID='2'"; 
  $query2 = mysqli_query($connection, $data2) or die("Couldn't execute query. ". mysql_error()); 
  
 $data3 = "UPDATE `settings` SET starttime='$sch3starttimestr', endtime='$sch3endtimestr', hightemp='$sch3hightemp', hightemprange='$sch3hightemprange', lowtemp='$sch3lowtemp', lowtemprange='$sch3lowtemprange', windowtemp='$sch3windowtemp', windowtemprange='$sch3windowtemprange', circfan='$sch3circfan'  WHERE ID='3'"; 
  $query3 = mysqli_query($connection, $data3) or die("Couldn't execute query. ". mysql_error()); 
  
 $data4 = "UPDATE `settings` SET starttime='$sch4starttimestr', hightemp='$sch4hightemp', hightemprange='$sch4hightemprange', lowtemp='$sch4lowtemp', lowtemprange='$sch4lowtemprange', windowtemp='$sch4windowtemp', windowtemprange='$sch4windowtemprange', circfan='$sch4circfan'  WHERE ID='4'"; 
  $query4 = mysqli_query($connection, $data4) or die("Couldn't execute query. ". mysql_error()); 
  }
?> 
 
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" 
"http://www.w3.org/TR/html4/loose.dtd"> 
<html> 
<head> 
	<meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Greenhouse Settings Confirmation</title> 

	<style type="text/css">
.error-style {
	color: #FA0000;
	font-size: x-large;
}
.wrap {
	width: 800px;
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
<br>
<?php if ($isformerror==1) { 
echo '<p class="error-style"><strong>Error: <br>'.$formerror.'</strong><br><br>The following settings were NOT Saved.</p>';
}
 ?>
<!--  display the changed record from database --> 
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
				<?php echo date("H:i", $sch1endtime)?></td>
			<td class="auto-style1" style="width: 88px">
				<?php echo $sch1hightemp ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch1hightemprange ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch1lowtemp ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch1lowtemprange ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch1windowtemp ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch1windowtemprange ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch1circfan ?></td>
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
				<?php echo date("H:i", $sch2starttime)?></td>
			<td class="auto-style1" style="width: 88">
				<?php echo date("H:i", $sch2endtime)?></td>
			<td class="auto-style1" style="width: 88px">
				<?php echo $sch2hightemp ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch2hightemprange ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch2lowtemp ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch2lowtemprange ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch2windowtemp ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch2windowtemprange ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch2circfan ?></td>
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
				<?php echo date("H:i", $sch3starttime)?></td>
			<td class="auto-style1" style="width: 88">
				<?php echo date("H:i", $sch3endtime)?></td>
			<td class="auto-style1" style="width: 88px">
				<?php echo $sch3hightemp ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch3hightemprange ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch3lowtemp ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch3lowtemprange ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch3windowtemp ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch3windowtemprange ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch3circfan ?></td>
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
				<?php echo date("H:i", $sch4starttime)?></td>
			<td class="auto-style1" style="width: 88">
				<?php echo date("H:i", $sch4endtime)?></td>
			<td class="auto-style1" style="width: 88px">
				<?php echo $sch4hightemp ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch4hightemprange ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch4lowtemp ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch4lowtemprange ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch4windowtemp ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch4windowtemprange ?></td>
			<td class="auto-style1" style="width: 89px">
				<?php echo $sch4circfan ?></td>
		</tr>
	</table><br>
  <br>

  <p><a href="settingsformsch.php">Back to Settings</a></p>
<p><a href="index.php">Home</a></p>
<br>
</div>
</body> 

</html> 
