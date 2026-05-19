<?php 
//MySQL Database Connect 
include 'dbconnect.php'; 

$windowoverridetime=$_POST['windowoverridetime']; 
$windowstatus=$_POST['windowstatus'];
$fanoverridetime=$_POST['fanoverridetime']; 
$fanstatus=$_POST['fanstatus'];

$isformerror = 0;
$formerror = "";

if ($windowstatus ==0) {
		$windowstatusname='Closed';
} else if ($windowstatus==1) {
		$windowstatusname='Open';
}
if ($fanstatus ==0) {
		$fanstatusname='Off';
} else if ($fanstatus ==1) {
		$fanstatusname='On';
}

$now = new DateTime();
$user_tz= 'America/Toronto';
$nowwindowutc=new DateTime($now->format('Y-m-d H:i:s'), new DateTimeZone($user_tz));
$nowwindowutc->setTimeZone(new DateTimeZone('UTC'));
$nowfanutc=new DateTime($now->format('Y-m-d H:i:s'), new DateTimeZone($user_tz));
$nowfanutc->setTimeZone(new DateTimeZone('UTC'));

if (empty($windowoverridetime))  {
	$formerror .= "No Window Change";
	$isformerror =1;
} else {	
$nowwindowutc->add(new DateInterval("PT{$windowoverridetime}M"));
$newwindow_time=$nowwindowutc->format('Y-m-d H:i:s');
$nowwindow2utc=$nowwindowutc;
$nowwindow2utc->setTimeZone(new DateTimeZone($user_tz));

$data = "UPDATE `overrides` SET windowoverride='$windowstatus', windowexpire='$newwindow_time' WHERE ID='1'"; 
  $query = mysqli_query($connection, $data) or die("Couldn't execute query. ". mysql_error()); 
}

if (empty($fanoverridetime))  {
	$formerror .= "<br>No Fan Change";
	$isformerror =1;
} else {	
$nowfanutc->add(new DateInterval("PT{$fanoverridetime}M"));
$newfan_time=$nowfanutc->format('Y-m-d H:i:s');
$nowfan2utc=$nowfanutc;
$nowfan2utc->setTimeZone(new DateTimeZone($user_tz));

$data = "UPDATE `overrides` SET fanoverride='$windowstatus', fanexpire='$newfan_time' WHERE ID='1'"; 
  $query = mysqli_query($connection, $data) or die("Couldn't execute query. ". mysql_error()); 
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
	width:300px;
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
	</style>

 </head> 

<body> 
<div class="wrap">
<br>
<?php if ($isformerror==1) { 
echo '<p class="error-style"><strong>'.$formerror.'</strong><br></p>';
}
 ?>
<!--  display the changed record from database --> 
<?php if (!empty($windowoverridetime))  {
	echo 'Window will remain <strong>'.$windowstatusname.'</strong> for <strong>'.$windowoverridetime.'</strong> minutes until <strong>'.$nowwindow2utc->format('D M d g:i a').'</strong>';
}?>
    <br>
<?php if (!empty($fanoverridetime))  {
	echo 'Fan will remain <strong>'.$fanstatusname.'</strong> for <strong>'.$fanoverridetime.'</strong> minutes until <strong>'.$nowfan2utc->format('D M d g:i a').'</strong>';
}?>
  <br>
  <p><a href="overrideform.php">Back to Settings</a></p>
<p><a href="index.php">Home</a></p>
<br>
</div>
</body> 

</html> 
