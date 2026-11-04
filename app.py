import re
from pathlib import Path

import pandas as pd
import streamlit as st

BaseDir = Path(__file__).resolve().parent
InventoriesDir = BaseDir / "inventaires"
DefaultInventoryName = "Inventaire"
# Only used to resolve older entries stored as paths relative to medias/
MediaDir = BaseDir / "medias"

ColPartNumber = "Numéro de pièce"
ColDescription = "Description"
ColManufacturer = "Manufacturier"
ColVendor1 = "Vendeur 1"
ColVendor2 = "Vendeur 2"
ColLocation = "Location"
ColNotes = "Note(s)"
ColTags = "Tags"
ColPhoto = "Photo"
ColPDF = "PDF"

Columns = [
    ColPartNumber,
    ColDescription,
    ColManufacturer,
    ColVendor1,
    ColVendor2,
    ColLocation,
    ColNotes,
    ColTags,
    ColPhoto,
    ColPDF,
]

PhotoExtensions = ["png", "jpg", "jpeg", "gif", "bmp", "webp"]
PDF_Extensions = ["pdf"]
AllLocationsLabel = "Toutes"
NewLocationLabel = "Nouvelle location..."
CSV_Encoding = "utf-8-sig"
# '|' cannot appear in Windows paths, so it safely separates multiple PDF paths
PathSeparator = "|"
TagSeparator = ","
# Above this count, the sidebar uses a dropdown instead of a list
MaxListedInventories = 8
MaxInventoryNameLength = 60
InvalidNameCharacters = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
ReservedWindowsNames = {"CON", "PRN", "AUX", "NUL"} | {f"COM{N}" for N in range(1, 10)} | {f"LPT{N}" for N in range(1, 10)}
SectionConsult = "Consulter l'inventaire"
SectionAdd = "Ajouter une pièce"

KeyPartNumber = "add_part_number"
KeyDescription = "add_description"
KeyManufacturer = "add_manufacturer"
KeyVendor1 = "add_vendor1"
KeyVendor2 = "add_vendor2"
KeyLocationChoice = "add_location_choice"
KeyNewLocation = "add_new_location"
KeyNotes = "add_notes"
KeyTags = "add_tags"
KeyPhoto = "add_photo"
KeyPDFs = "add_pdfs"
AddFormKeys = [
    KeyPartNumber,
    KeyDescription,
    KeyManufacturer,
    KeyVendor1,
    KeyVendor2,
    KeyLocationChoice,
    KeyNewLocation,
    KeyNotes,
    KeyTags,
    KeyPhoto,
    KeyPDFs,
]
KeyResetAddForm = "reset_add_form"
KeyAddSuccessMessage = "add_success_message"
KeyPendingDelete = "pending_delete"
KeyDeleteMessage = "delete_message"
KeyCurrentInventory = "current_inventory"
KeyInventoryToSelect = "inventory_to_select"
KeyNewInventoryName = "new_inventory_name"
KeyRenameInventory = "rename_inventory_name"
KeyInventoryMessage = "inventory_message"


def InitializeStorage():
    InventoriesDir.mkdir(parents=True, exist_ok=True)
    if len(ListInventories()) == 0:
        CreateInventory(DefaultInventoryName)


def ListInventories():
    return sorted((File.stem for File in InventoriesDir.glob("*.csv")), key=str.lower)


def GetInventoryPath(Name):
    return InventoriesDir / f"{Name}.csv"


def ValidateInventoryName(RawName, CurrentName=""):
    Name = RawName.strip()
    if Name == "":
        raise ValueError("Le nom de l'inventaire est obligatoire.")
    if len(Name) > MaxInventoryNameLength:
        raise ValueError(f"Le nom ne doit pas dépasser {MaxInventoryNameLength} caractères.")
    # The name becomes a file name, so block path separators and Windows-invalid names
    if InvalidNameCharacters.search(Name) is not None or Name.endswith("."):
        raise ValueError('Le nom ne peut pas contenir \\ / : * ? " < > | ni finir par un point.')
    if Name.upper() in ReservedWindowsNames:
        raise ValueError(f"« {Name} » est un nom réservé par Windows.")

    ExistingNames = {Existing.lower() for Existing in ListInventories() if Existing != CurrentName}
    if Name.lower() in ExistingNames:
        raise ValueError(f"L'inventaire « {Name} » existe déjà.")
    return Name


def CreateInventory(Name):
    pd.DataFrame(columns=Columns).to_csv(GetInventoryPath(Name), index=False, encoding=CSV_Encoding)


def LoadInventory(CSV_Path):
    try:
        Data = pd.read_csv(CSV_Path, dtype=str, keep_default_na=False, encoding=CSV_Encoding)
    except pd.errors.EmptyDataError:
        Data = pd.DataFrame(columns=Columns)

    # Add any missing column so older or hand-edited files remain usable
    for Column in Columns:
        if Column not in Data.columns:
            Data[Column] = ""
    return Data[Columns]


def SaveInventory(Data, CSV_Path):
    Data.to_csv(CSV_Path, index=False, encoding=CSV_Encoding)


def ValidateReference(RawPath, AllowedExtensions, Kind):
    # Windows "Copy as path" wraps the path in double quotes
    CleanPath = RawPath.strip().strip('"').strip()
    if CleanPath == "":
        return ""

    Candidate = Path(CleanPath)
    if Candidate.is_absolute() == False:
        raise ValueError(f"Le chemin {Kind} doit être absolu (ex. \\\\serveur\\partage\\fichier) : {CleanPath}")
    if Candidate.suffix.lower().lstrip(".") not in AllowedExtensions:
        raise ValueError(f"Extension non autorisée pour le fichier {Kind} : {CleanPath}")
    if Candidate.is_file() == False:
        raise ValueError(f"Fichier {Kind} introuvable : {CleanPath}")
    return str(Candidate)


def ResolveMediaPath(RelativePath):
    if RelativePath.strip() == "":
        return None

    FullPath = (BaseDir / RelativePath).resolve()
    # Only serve files located inside the media folder
    if FullPath.is_relative_to(MediaDir.resolve()) == False:
        return None
    if FullPath.is_file() == False:
        return None
    return FullPath


def ResolveReference(StoredPath, AllowedExtensions):
    if StoredPath.strip() == "":
        return None

    Candidate = Path(StoredPath)
    if Candidate.is_absolute() == False:
        return ResolveMediaPath(StoredPath)

    # Referenced files are only served if their type is expected
    if Candidate.suffix.lower().lstrip(".") not in AllowedExtensions:
        return None
    try:
        if Candidate.is_file() == False:
            return None
    except OSError:
        return None
    return Candidate


def SplitPaths(StoredValue):
    return [Value.strip() for Value in StoredValue.split(PathSeparator) if Value.strip() != ""]


def GetLocations(Data):
    Locations = sorted({Value.strip() for Value in Data[ColLocation] if Value.strip() != ""})
    return Locations


def SplitTags(StoredValue):
    return [Value.strip() for Value in StoredValue.split(TagSeparator) if Value.strip() != ""]


def NormalizeTags(Tags):
    # Deduplicate case-insensitively while keeping the first spelling entered
    UniqueTags = {}
    for Tag in Tags:
        Clean = Tag.replace(TagSeparator, " ").strip()
        if Clean != "" and Clean.lower() not in UniqueTags:
            UniqueTags[Clean.lower()] = Clean
    return list(UniqueTags.values())


def GetTags(Data):
    AllTags = [Tag for Value in Data[ColTags] for Tag in SplitTags(Value)]
    return sorted(NormalizeTags(AllTags), key=str.lower)


def HasAllTags(StoredValue, SelectedTags):
    RowTags = {Tag.lower() for Tag in SplitTags(StoredValue)}
    return all(Tag.lower() in RowTags for Tag in SelectedTags)


def ShowPartCard(Row, Index, CSV_Path):
    with st.container(border=True):
        LeftCol, RightCol = st.columns([1, 2])

        with LeftCol:
            PhotoPath = ResolveReference(Row[ColPhoto], PhotoExtensions)
            if PhotoPath is not None:
                st.image(PhotoPath.read_bytes(), width="stretch")
            elif Row[ColPhoto].strip() != "":
                st.caption(f"Photo inaccessible : {Row[ColPhoto]}")
            else:
                st.caption("Aucune photo")

            StoredPDFs = SplitPaths(Row[ColPDF])
            for PDF_Number, StoredPDF in enumerate(StoredPDFs):
                PDF_Path = ResolveReference(StoredPDF, PDF_Extensions)
                if PDF_Path is None:
                    st.caption(f"PDF inaccessible : {StoredPDF}")
                    continue
                st.download_button(
                    label=f"Télécharger {PDF_Path.name}",
                    data=PDF_Path.read_bytes(),
                    file_name=PDF_Path.name,
                    mime="application/pdf",
                    key=f"pdf_{Index}_{PDF_Number}",
                )
            if len(StoredPDFs) == 0:
                st.caption("Aucun PDF")

        with RightCol:
            st.subheader(Row[ColPartNumber])
            st.markdown(f"**Manufacturier :** {Row[ColManufacturer] or '-'}")
            st.markdown(f"**Location :** {Row[ColLocation] or '-'}")
            st.markdown(f"**Vendeur 1 :** {Row[ColVendor1] or '-'}")
            st.markdown(f"**Vendeur 2 :** {Row[ColVendor2] or '-'}")
            RowTags = SplitTags(Row[ColTags])
            if len(RowTags) > 0:
                st.markdown("**Tags :** " + " ".join(f"`{Tag}`" for Tag in RowTags))
            if Row[ColDescription].strip() != "":
                st.markdown("**Description :**")
                st.text(Row[ColDescription])
            if Row[ColNotes].strip() != "":
                st.markdown("**Note(s) :**")
                st.text(Row[ColNotes])

            ShowDeleteControls(Row[ColPartNumber], Index, CSV_Path)


def DeletePart(PartNumber, CSV_Path):
    Data = LoadInventory(CSV_Path)
    Data = Data[Data[ColPartNumber].str.strip() != PartNumber.strip()]
    SaveInventory(Data, CSV_Path)


def ShowDeleteControls(PartNumber, Index, CSV_Path):
    PendingTarget = (str(CSV_Path), PartNumber)
    if st.session_state.get(KeyPendingDelete) != PendingTarget:
        if st.button("Supprimer", key=f"delete_{Index}"):
            st.session_state[KeyPendingDelete] = PendingTarget
            st.rerun()
        return

    st.warning(f"Supprimer définitivement « {PartNumber} » ? Les fichiers référencés ne sont pas effacés.")
    ConfirmCol, CancelCol = st.columns(2)
    with ConfirmCol:
        if st.button("Confirmer la suppression", key=f"confirm_delete_{Index}", type="primary"):
            try:
                DeletePart(PartNumber, CSV_Path)
            except OSError as Error:
                st.error(f"Impossible d'écrire dans {CSV_Path.name} : {Error}")
                return
            st.session_state.pop(KeyPendingDelete, None)
            st.session_state[KeyDeleteMessage] = f"Pièce « {PartNumber} » supprimée."
            st.rerun()
    with CancelCol:
        if st.button("Annuler", key=f"cancel_delete_{Index}"):
            st.session_state.pop(KeyPendingDelete, None)
            st.rerun()


def ShowConsultSection(CSV_Path):
    st.header(f"Consulter l'inventaire « {CSV_Path.stem} »")
    Data = LoadInventory(CSV_Path)

    DeleteMessage = st.session_state.pop(KeyDeleteMessage, "")
    if DeleteMessage != "":
        st.success(DeleteMessage)

    if Data.empty:
        st.info("L'inventaire est vide. Ajoutez une pièce dans la section « Ajouter une pièce ».")
        return

    FilterCol, TagCol, SearchCol = st.columns([1, 1, 2])
    with FilterCol:
        SelectedLocation = st.selectbox("Filtrer par location", [AllLocationsLabel] + GetLocations(Data))
    with TagCol:
        SelectedTags = st.multiselect("Filtrer par tags", GetTags(Data), placeholder="Tous")
    with SearchCol:
        SearchText = st.text_input(
            "Recherche globale",
            placeholder="Numéro de pièce, manufacturier, tag ou mot-clé de la description",
        )

    Filtered = Data
    if SelectedLocation != AllLocationsLabel:
        Filtered = Filtered[Filtered[ColLocation].str.strip() == SelectedLocation]

    if len(SelectedTags) > 0:
        Filtered = Filtered[Filtered[ColTags].apply(HasAllTags, args=(SelectedTags,))]

    SearchText = SearchText.strip()
    if SearchText != "":
        Mask = (
            Filtered[ColPartNumber].str.contains(SearchText, case=False, regex=False)
            | Filtered[ColManufacturer].str.contains(SearchText, case=False, regex=False)
            | Filtered[ColDescription].str.contains(SearchText, case=False, regex=False)
            | Filtered[ColTags].str.contains(SearchText, case=False, regex=False)
        )
        Filtered = Filtered[Mask]

    st.write(f"**{len(Filtered)}** pièce(s) trouvée(s)")
    if Filtered.empty:
        return

    ViewMode = st.radio("Affichage", ["Fiches", "Tableau"], horizontal=True)
    if ViewMode == "Tableau":
        st.dataframe(
            Filtered.drop(columns=[ColPhoto, ColPDF]),
            width="stretch",
            hide_index=True,
        )
    else:
        for Index, Row in Filtered.iterrows():
            ShowPartCard(Row, Index, CSV_Path)


def ShowAddSection(CSV_Path):
    st.header(f"Ajouter une pièce à « {CSV_Path.stem} »")
    Data = LoadInventory(CSV_Path)
    ExistingLocations = GetLocations(Data)

    # Widget state can only be cleared before the widgets are created, hence the rerun
    if st.session_state.pop(KeyResetAddForm, False) == True:
        for Key in AddFormKeys:
            st.session_state.pop(Key, None)

    SuccessMessage = st.session_state.pop(KeyAddSuccessMessage, "")
    if SuccessMessage != "":
        st.success(SuccessMessage)

    with st.form("add_part_form", clear_on_submit=False):
        PartNumber = st.text_input("Numéro de pièce *", key=KeyPartNumber)
        Description = st.text_area("Description", key=KeyDescription)

        Col1, Col2, Col3 = st.columns(3)
        with Col1:
            Manufacturer = st.text_input("Manufacturier", key=KeyManufacturer)
        with Col2:
            Vendor1 = st.text_input("Vendeur 1", key=KeyVendor1)
        with Col3:
            Vendor2 = st.text_input("Vendeur 2", key=KeyVendor2)

        LocCol1, LocCol2 = st.columns(2)
        with LocCol1:
            LocationChoice = st.selectbox(
                "Location existante",
                [NewLocationLabel] + ExistingLocations,
                key=KeyLocationChoice,
            )
        with LocCol2:
            NewLocation = st.text_input("Nouvelle location (prioritaire si remplie)", key=KeyNewLocation)

        Notes = st.text_area("Note(s)", key=KeyNotes)

        Tags = st.multiselect(
            "Tags (choisir ou taper un nouveau tag puis Entrée)",
            GetTags(Data),
            accept_new_options=True,
            placeholder="ex. MCU, ARM, connecteur, résistance, SMD",
            key=KeyTags,
        )

        PhotoReference = st.text_input(
            "Chemin de la photo",
            placeholder=r"\\serveur\partage\photo.jpg",
            key=KeyPhoto,
        )
        PDF_References = st.text_area(
            "Chemins des fiches techniques PDF (un par ligne)",
            placeholder=r"\\serveur\partage\fiche.pdf",
            key=KeyPDFs,
        )

        Submitted = st.form_submit_button("Enregistrer la pièce")

    if Submitted == False:
        return

    PartNumber = PartNumber.strip()
    if PartNumber == "":
        st.error("Le numéro de pièce est obligatoire.")
        return

    ExistingNumbers = Data[ColPartNumber].str.strip().str.lower()
    if PartNumber.lower() in ExistingNumbers.values:
        st.error(f"Le numéro de pièce « {PartNumber} » existe déjà.")
        return

    Location = NewLocation.strip()
    if Location == "" and LocationChoice != NewLocationLabel:
        Location = LocationChoice

    try:
        PhotoPath = ValidateReference(PhotoReference, PhotoExtensions, "photo")
        PDF_Paths = [ValidateReference(Line, PDF_Extensions, "PDF") for Line in PDF_References.splitlines()]
        PDF_Paths = [Value for Value in PDF_Paths if Value != ""]
    except (ValueError, OSError) as Error:
        st.error(f"Erreur de référence de fichier : {Error}")
        return

    NewRow = {
        ColPartNumber: PartNumber,
        ColDescription: Description.strip(),
        ColManufacturer: Manufacturer.strip(),
        ColVendor1: Vendor1.strip(),
        ColVendor2: Vendor2.strip(),
        ColLocation: Location,
        ColNotes: Notes.strip(),
        ColTags: TagSeparator.join(NormalizeTags(Tags)),
        ColPhoto: PhotoPath,
        ColPDF: PathSeparator.join(PDF_Paths),
    }

    Data = pd.concat([Data, pd.DataFrame([NewRow])], ignore_index=True)
    try:
        SaveInventory(Data, CSV_Path)
    except OSError as Error:
        st.error(f"Impossible d'écrire dans {CSV_Path.name} : {Error}")
        return

    st.session_state[KeyAddSuccessMessage] = f"Pièce « {PartNumber} » ajoutée avec succès."
    st.session_state[KeyResetAddForm] = True
    st.rerun()


def SelectInventoryOnNextRun(Name, Message):
    st.session_state[KeyInventoryToSelect] = Name
    st.session_state[KeyInventoryMessage] = Message
    st.rerun()


def ShowInventorySelector():
    Inventories = ListInventories()

    # Widget state can only be changed before the widget is created
    PendingSelection = st.session_state.pop(KeyInventoryToSelect, None)
    if PendingSelection is not None:
        st.session_state[KeyCurrentInventory] = PendingSelection
    if st.session_state.get(KeyCurrentInventory) not in Inventories:
        st.session_state[KeyCurrentInventory] = Inventories[0]

    st.sidebar.title("Inventaires")
    if len(Inventories) <= MaxListedInventories:
        CurrentName = st.sidebar.radio(
            "Inventaires",
            Inventories,
            key=KeyCurrentInventory,
            label_visibility="collapsed",
        )
    else:
        CurrentName = st.sidebar.selectbox(
            "Inventaires",
            Inventories,
            key=KeyCurrentInventory,
            label_visibility="collapsed",
        )

    InventoryMessage = st.session_state.pop(KeyInventoryMessage, "")
    if InventoryMessage != "":
        st.sidebar.success(InventoryMessage)

    with st.sidebar.expander("Nouvel inventaire"):
        NewName = st.text_input("Nom", placeholder="ex. Électronique, Arts", key=KeyNewInventoryName)
        if st.button("Créer", key="create_inventory"):
            try:
                Name = ValidateInventoryName(NewName)
                CreateInventory(Name)
            except (ValueError, OSError) as Error:
                st.error(str(Error))
            else:
                SelectInventoryOnNextRun(Name, f"Inventaire « {Name} » créé.")

    with st.sidebar.expander("Renommer cet inventaire"):
        RenamedName = st.text_input("Nouveau nom", placeholder=CurrentName, key=KeyRenameInventory)
        if st.button("Renommer", key="rename_inventory"):
            try:
                Name = ValidateInventoryName(RenamedName, CurrentName)
                GetInventoryPath(CurrentName).rename(GetInventoryPath(Name))
            except (ValueError, OSError) as Error:
                st.error(str(Error))
            else:
                SelectInventoryOnNextRun(Name, f"Inventaire renommé en « {Name} ».")

    return GetInventoryPath(CurrentName)


def Main():
    st.set_page_config(page_title="Inventaire de pièces", layout="wide")
    InitializeStorage()

    CSV_Path = ShowInventorySelector()
    st.sidebar.divider()
    Section = st.sidebar.radio("Navigation", [SectionConsult, SectionAdd])

    if Section == SectionConsult:
        ShowConsultSection(CSV_Path)
    else:
        ShowAddSection(CSV_Path)


if __name__ == "__main__":
    Main()
