plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// The address the app opens. CI can point a build at another deployment with -PsiteUrl=...
val siteUrl: String = (project.findProperty("siteUrl") as String?) ?: "https://pashupatastra.vercel.app"
// The public API the native screens read (the same one the site reads, NEXT_PUBLIC_API_URL).
val apiUrl: String = (project.findProperty("apiUrl") as String?) ?: "https://265d0hsmwa.execute-api.us-east-1.amazonaws.com/api/v1"

android {
    namespace = "app.pashupatastra"
    compileSdk = 35

    defaultConfig {
        applicationId = "app.pashupatastra"
        minSdk = 24
        targetSdk = 35
        // CI sets the build number from the run, so each APK installs over the last.
        versionCode = ((project.findProperty("versionCode") as String?) ?: "1").toInt()
        versionName = (project.findProperty("versionName") as String?) ?: "0.1"
        buildConfigField("String", "SITE_URL", "\"$siteUrl\"")
        buildConfigField("String", "API_URL", "\"$apiUrl\"")
        // The support address the More sheet's "Contact support" opens (owner, 2 Nov 2026). Override with
        // -PsupportEmail=...; an empty value hides the row.
        buildConfigField("String", "SUPPORT_EMAIL", "\"${(project.findProperty("supportEmail") as String?) ?: "preetraval45@gmail.com"}\"")
    }

    signingConfigs {
        // A PUBLIC test key, committed on purpose so every CI build can install over the previous one.
        // It is for sideloaded test builds only. A store release gets its own private key, held as a
        // GitHub secret, never this one.
        create("test") {
            storeFile = rootProject.file("test-signing.jks")
            storePassword = "android"
            keyAlias = "pashupatastra-test"
            keyPassword = "android"
        }
        // The Play Store upload key: private, never committed. CI writes it from the
        // UPLOAD_KEYSTORE_BASE64 secret and passes the passwords as environment variables.
        System.getenv("UPLOAD_STORE_FILE")?.let { path ->
            create("upload") {
                storeFile = file(path)
                storePassword = System.getenv("UPLOAD_STORE_PASSWORD")
                keyAlias = System.getenv("UPLOAD_KEY_ALIAS")
                keyPassword = System.getenv("UPLOAD_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            // -Pplay signs with the private upload key, for the store; otherwise the public test key.
            signingConfig = signingConfigs.getByName(if (project.hasProperty("play")) "upload" else "test")
        }
    }

    buildFeatures {
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.activity:activity-ktx:1.9.3")
    implementation("androidx.swiperefreshlayout:swiperefreshlayout:1.1.0")
    implementation("androidx.webkit:webkit:1.12.1")
    implementation("androidx.core:core-splashscreen:1.0.1")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.work:work-runtime-ktx:2.9.1")
    implementation("androidx.biometric:biometric:1.1.0")
}
