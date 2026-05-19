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
  
$settingsdata = 'SELECT * FROM `settings` WHERE `ID` = 1'; 
  $settingsquery = mysqli_query($connection, $settingsdata) or die("Couldn't execute query. ". mysql_error());
  $settingsdata2 = mysqli_fetch_array($settingsquery);

$settings2data = 'SELECT * FROM `settings` WHERE `ID` = 2'; 
  $settings2query = mysqli_query($connection, $settings2data) or die("Couldn't execute query. ". mysql_error());
  $settings2data2 = mysqli_fetch_array($settings2query);

$settings3data = 'SELECT * FROM `settings` WHERE `ID` = 3'; 
  $settings3query = mysqli_query($connection, $settings3data) or die("Couldn't execute query. ". mysql_error());
  $settings3data2 = mysqli_fetch_array($settings3query);

$settings4data = 'SELECT * FROM `settings` WHERE `ID` = 4'; 
  $settings4query = mysqli_query($connection, $settings4data) or die("Couldn't execute query. ". mysql_error());
  $settings4data2 = mysqli_fetch_array($settings4query);
  
 $statusdata = 'SELECT * FROM `status` WHERE `ID` = 1'; 
  $statusquery = mysqli_query($connection, $statusdata) or die("Couldn't execute query. ". mysql_error());
  $statusdata2 = mysqli_fetch_array($statusquery);
  
$overridedata = 'SELECT * FROM `overrides` WHERE `ID` = 1'; 
  $overridequery = mysqli_query($connection, $overridedata) or die("Couldn't execute query. ". mysql_error());
  $overridedata2 = mysqli_fetch_array($overridequery);

 $utc = new DateTimeZone('UTC');
 $timezone = new DateTimeZone('America/Toronto');
 $now = new DateTime(null, $utc);
 $given = new DateTime($temp1data2['timestamp'], $utc);
 $interval = $now->diff($given, true);

 $windowexpire = new DateTime($overridedata2['windowexpire'], $utc);
 $fanexpire = new DateTime($overridedata2['fanexpire'], $utc);
 
 $sch1endtime = new DateTime ($settingsdata2['endtime'], $timezone);
 $sch2endtime = new DateTime ($settings2data2['endtime'], $timezone);
 $sch3endtime = new DateTime ($settings3data2['endtime'], $timezone);
 $sch4endtime = new DateTime ($settings4data2['endtime'], $timezone);
 
 if ($now < $sch1endtime) {
	 $schedule=1;
 } elseif ($now < $sch2endtime){
	 $schedule=2;
 } elseif ($now < $sch3endtime) {
	 $schedule=3;
 } elseif ($now < $sch4endtime) {
	 $schedule=4;
 }

  ?> 
<table style="width: 300px" align="center">

	<tr>
		<td class="auto-style4" colspan="2">Currently Running on <br> Schedule <?php echo $schedule?> <br><br></td>
	</tr>
	<tr>
		<td class="auto-style4" colspan="2"><strong>Heater</strong></td>
	</tr>
	<tr>
	<?php
	if ($statusdata2['heater']==0) {
		echo '<td class="auto-style7" style="width: 199px"><img alt="ON" height="25" src="images/off.gif" width="50"></td>';
	} elseif ($statusdata2['heater']==1) {
		echo '<td class="auto-style7" style="width: 199px"><img alt="Fan" height="50" src="images/fire.gif" width="50"><br>';
		echo '<img alt="ON" height="25" src="images/on.gif" width="50"></td>';
	} else {
		echo '<td class="auto-style7" style="width: 199px">ERROR</td>';
	}
	?>
		<td class="auto-style9" style="width: 199px">Set Point: 
		<?php 
		if ($schedule==1) {
			echo $settingsdata2['lowtemp'];
		} elseif ($schedule==2) {
			echo $settings2data2['lowtemp'];
		} elseif ($schedule==3) {
			echo $settings3data2['lowtemp'];
		} elseif ($schedule==4) {
			echo $settings4data2['lowtemp'];
		}
		?>
		&deg; C</td>
	</tr>
	<tr>
		<td class="auto-style4" colspan="2"><br><strong>Ventilation Fan</strong></td>
	</tr>
	<tr>
	<?php
	if ($statusdata2['fan']==0) {
		echo '<td class="auto-style7" style="width: 199px"><img alt="Fan" height="52" src="images/Fan_static.jpg" width="50"><br>';
		echo '<img alt="ON" height="25" src="images/off.gif" width="50"></td>';
	} elseif ($statusdata2['fan']==1) {
		echo '<td class="auto-style7" style="width: 199px"><img alt="Fan" height="52" src="images/Fan_Animation.gif" width="50"><br>';
		echo '<img alt="ON" height="25" src="images/on.gif" width="50"></td>';
	}else {
		echo '<td class="auto-style7" style="width: 199px">ERROR</td>';
	}
	?>
		<td class="auto-style9" style="width: 199px">Set Point: 
		<?php 
		if ($schedule==1) {
			echo $settingsdata2['hightemp'];
		} elseif ($schedule==2) {
			echo $settings2data2['hightemp'];
		} elseif ($schedule==3) {
			echo $settings3data2['hightemp'];
		} elseif ($schedule==4) {
			echo $settings4data2['hightemp'];
		}
		?>&deg; C<br>

		<?php	 
		if ( $fanexpire > $given) {
		echo '<img alt="Override" height="25" src="images/override.gif" width="93">';
		echo '<br> <a href="#" onclick="cancelfanoverride();">Cancel Override</a>';
	}	else {
		echo '<a href="overrideform.php">Override</a>';
	}?>
		
		</td>
	</tr>
	<tr>
		<td class="auto-style4" colspan="2"><br><strong>Window</strong></td>
	</tr>
	<tr>
	<?php
	if ($statusdata2['window']==0) {
		echo '<td class="auto-style7" style="width: 199px"><img alt="Fan" height="100" src="images/windowclosed.gif" width="85"><br>';
		echo '<img alt="ON" height="25" src="images/closed.gif" width="50"></td>';
	} elseif ($statusdata2['window']==1) {
		echo '<td class="auto-style7" style="width: 199px"><img alt="Fan" height="81" src="images/windowopen.gif" width="100"><br>';
		echo '<img alt="ON" height="25" src="images/open.gif" width="50"></td>';
	} else {
		echo '<td class="auto-style7" style="width: 199px">ERROR</td>';
	}
	?>
		<td class="auto-style9" style="width: 199px">Set Point: 
		<?php
		if ($schedule==1) {
			echo $settingsdata2['windowtemp'];
		} elseif ($schedule==2) {
			echo $settings2data2['windowtemp'];
		} elseif ($schedule==3) {
			echo $settings3data2['windowtemp'];
		} elseif ($schedule==4) {
			echo $settings4data2['windowtemp'];
		}
		?>&deg; C<br>
			<?php	 
	if ( $windowexpire > $given) {
		echo '<img alt="Override" height="25" src="images/override.gif" width="93">';
		echo '<br> <a href="#" onclick="cancelwindowoverride();">Cancel Override</a>';
	}	else {
		echo '<a href="overrideform.php">Override</a>';
	}?>
	</td>
	</tr>
		<tr>
		<td class="auto-style4" colspan="2"><br><strong>Circulation Fan</strong></td>
	</tr>
	<tr>
	<?php
	if ($statusdata2['circfan']==0) {
		echo '<td class="auto-style7" style="width: 199px"><img alt="Fan" height="90" src="images/circfanoff.jpg" width="80"><br>';
		echo '<img alt="ON" height="25" src="images/off.gif" width="50"></td>';
	} elseif ($statusdata2['circfan']==1) {
		echo '<td class="auto-style7" style="width: 199px"><img alt="Fan" height="90" src="images/circfanon.gif" width="80"><br>';
		echo '<img alt="ON" height="25" src="images/on.gif" width="50"></td>';
	}else {
		echo '<td class="auto-style7" style="width: 199px">ERROR</td>';
	}
	?>
		<td class="auto-style9" style="width: 199px"></td>
	</tr>
	<tr>
		<td class="auto-style5" style="width: 199px">&nbsp;</td>
		<td class="auto-style6" style="width: 199px">&nbsp;</td>
	</tr>
	<tr>
		<td class="auto-style9" style="width: 199px"><a href="graphs.php">Graphs</a></td>
		<td class="auto-style9" style="width: 199px"><a href="settingsformsch.php">
		Settings</a></td>
	</tr>
	<tr>
		<td class="auto-style9" style="width: 199px"></td>
		<td class="auto-style9" style="width: 199px"><a href="overrideform.php">
		Override Settings</a></td>
	</tr>
	<tr>
		<td class="centre-style" colspan="2">
		<?php $seconds=($interval->d*86400)+($interval->h*3600)+($interval->i*60)+$interval->s;
		echo '<p class="centre-style"> Data Last Updated ', $seconds, ' Seconds Ago </p>';
		?>
		</td>
	</tr>
</table>

